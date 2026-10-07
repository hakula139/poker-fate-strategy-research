import asyncio
import hashlib
import logging
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosedOK

from .capture import Capture
from .packets import Packet, pack, unpack
from .practice import Practice
from .schema import Schema
from .session import Session


class ClientError(Exception):
    pass


@dataclass(frozen=True)
class Observation:
    duration: float = 60
    login_timeout: float = 30
    room_id: int | None = None
    practice: Practice | None = None

    def __post_init__(self) -> None:
        if not all(
            math.isfinite(value) and value > 0
            for value in (
                self.duration,
                self.login_timeout,
            )
        ):
            raise ValueError('Observation and login timeouts must be positive.')

        if self.room_id is not None and not 0 < self.room_id < 2**31:
            raise ValueError('Room ID must be a positive int32.')

        if self.room_id is not None and self.practice is not None:
            raise ValueError('Choose either an existing room or a new training entry.')


class ProtocolClient:
    def __init__(
        self,
        socket: ClientConnection,
        schema: Schema,
        session: Session,
        capture: Capture,
        options: Observation,
    ) -> None:
        self.socket = socket
        self.schema = schema
        self.session = session
        self.capture = capture
        self.options = options
        self.logged_in = False
        self.room_id = 0
        self.snapshot_received = False

    async def send(self, name: str, fields: dict[str, Any], room_id: int = 0) -> None:
        packet = Packet(name, room_id, self.schema.encode(name, fields))
        await self.socket.send(pack(packet))
        self.capture.packet(
            packet, 'sent', datetime.now(UTC).isoformat(), time.monotonic_ns()
        )

    async def handle(self, packet: Packet) -> None:
        if packet.name == 'pb.UserLoginRSP':
            await self._login(self.schema.decode(packet.name, packet.payload))
        elif packet.name in {
            'pb.QuickStartRSP',
            'pb.EnterRoomRSP',
            'pb.GetRoomDataRSP',
        }:
            self._room_response(packet)
        elif packet.name in {'pb.UserLogoutRSP', 'pb.ServerStopBRC'}:
            raise ClientError('Server ended the session.')

    async def _login(self, fields: dict[str, Any]) -> None:
        code = fields.get('code', 0)
        self.capture.event('login-status', code=code)
        if code == 1002:
            return

        if code != 0:
            raise ClientError(f'WebSocket login rejected with code {code}.')

        if self.logged_in:
            return

        self.logged_in = True
        if self.options.room_id is not None:
            await self.send(
                'pb.GetRoomDataREQ',
                {'roomid': self.options.room_id},
                self.options.room_id,
            )
        elif self.options.practice is not None:
            await self.send(
                'pb.QuickStartREQ', self.options.practice.fields(self.session)
            )

    def _room_response(self, packet: Packet) -> None:
        fields = self.schema.decode(packet.name, packet.payload)
        code = fields.get('code', 0)
        if code != 0:
            raise ClientError(f'Room request rejected with code {code}.')

        if packet.name == 'pb.QuickStartRSP':
            return

        self.room_id = int(fields.get('roomid', 0))
        if self.room_id <= 0:
            raise ClientError('Room response has no positive room ID.')

        if packet.name == 'pb.GetRoomDataRSP' and self.options.room_id is not None:
            if self.room_id != self.options.room_id:
                raise ClientError('Snapshot response belongs to another room.')

            self.snapshot_received = True

        if self.options.practice and fields.get('game_type') != 40010101:
            raise ClientError('Server entered a different game type than training.')

        self.capture.event('room-ready', room_id=self.room_id)

    def ensure_ready(self) -> None:
        if not self.logged_in:
            raise ClientError('Observation ended before login succeeded.')

        if self.options.room_id is not None and not self.snapshot_received:
            raise ClientError(
                'Observation ended before the requested snapshot arrived.'
            )

        if self.options.practice is not None and not self.room_id:
            raise ClientError('Observation ended before the requested room was ready.')

    async def _receive(self, timeout: float) -> None:
        frame = await asyncio.wait_for(self.socket.recv(), timeout)
        observed_at = datetime.now(UTC).isoformat()
        monotonic_ns = time.monotonic_ns()
        if not isinstance(frame, bytes):
            raise ClientError('Expected a binary protocol frame.')

        try:
            packets = unpack(frame)
        except ValueError as error:
            self.capture.event(
                'framing-error',
                direction='received',
                observed_at=observed_at,
                monotonic_ns=monotonic_ns,
                frame_size=len(frame),
                error_type=type(error).__name__,
            )
            raise ClientError('Received a malformed protocol frame.') from error

        for packet in packets:
            self.capture.packet(packet, 'received', observed_at, monotonic_ns)

        for packet in packets:
            await self.handle(packet)

    async def run(self) -> None:
        await self.send(
            'pb.UserLoginREQ',
            {
                'uid': self.session.uid,
                'key': self.session.rdkey,
                'ver': self.session.version,
                'chnl': self.session.channel,
            },
        )
        loop = asyncio.get_running_loop()
        start = loop.time()
        end = start + self.options.duration
        login_deadline = start + self.options.login_timeout
        heartbeat = start + 5
        while loop.time() < end:
            now = loop.time()
            if not self.logged_in and now >= login_deadline:
                raise ClientError('WebSocket login timed out while waiting or queued.')

            if now >= heartbeat:
                await self.send('pb.HeartBeatREQ', {}, self.room_id)
                heartbeat = loop.time() + 5

            deadline = min(end, heartbeat)
            if not self.logged_in:
                deadline = min(deadline, login_deadline)

            try:
                await self._receive(deadline - loop.time())
            except TimeoutError:
                continue

        self.ensure_ready()


async def observe(
    session: Session,
    descriptors: bytes,
    output: Path,
    options: Observation,
) -> None:
    schema = Schema(descriptors)
    logger = logging.Logger('poker-fate-transport')
    logger.addHandler(logging.NullHandler())
    with Capture(output, schema, session) as capture:
        capture.event(
            'start',
            schema_sha256=hashlib.sha256(descriptors).hexdigest(),
            version=session.version,
            channel=session.channel,
            mode='practice' if options.practice else 'observe',
        )
        try:
            async with connect(
                session.server_url,
                proxy=None,
                ping_interval=None,
                logger=logger,
            ) as socket:
                client = ProtocolClient(socket, schema, session, capture, options)
                await client.run()
        except ConnectionClosedOK:
            try:
                client.ensure_ready()
            except ClientError:
                capture.event('end', status='failed', error_type='ClientError')
                raise

            capture.event('end', status='closed')
        except BaseException as error:
            capture.event(
                'end',
                status='interrupted'
                if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError))
                else 'failed',
                error_type=type(error).__name__,
            )
            raise
        else:
            capture.event('end', status='duration-complete')
