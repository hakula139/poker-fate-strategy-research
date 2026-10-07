import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from websockets.asyncio.server import ServerConnection, serve

from poker_fate_strategy_research.client import ClientError, Observation, observe
from poker_fate_strategy_research.packets import Packet, pack, unpack
from poker_fate_strategy_research.practice import Practice
from poker_fate_strategy_research.schema import Schema
from poker_fate_strategy_research.session import Session


async def receive(socket: ServerConnection) -> Packet:
    frame = await socket.recv()
    assert isinstance(frame, bytes)
    return unpack(frame)[0]


async def reply(
    socket: ServerConnection,
    schema: Schema,
    name: str,
    fields: dict[str, object],
    room_id: int = 0,
) -> None:
    await socket.send(pack(Packet(name, room_id, schema.encode(name, fields))))


def test_queued_training_and_heartbeat(
    tmp_path: Path,
    descriptors: bytes,
    session: Session,
) -> None:
    schema = Schema(descriptors)
    requests = []

    async def server(socket: ServerConnection) -> None:
        packet = await receive(socket)
        assert schema.decode(packet.name, packet.payload) == {
            'uid': '1234',
            'key': session.rdkey,
            'ver': '1.7.0',
            'chnl': 3,
        }
        await reply(socket, schema, 'pb.UserLoginRSP', {'code': 1002})
        heartbeat = await receive(socket)
        requests.append(heartbeat.name)
        assert heartbeat.name == 'pb.HeartBeatREQ' and heartbeat.room_id == 0
        await reply(socket, schema, 'pb.UserLoginRSP', {'code': 0})
        start = await receive(socket)
        requests.append(start.name)
        assert start.name == 'pb.QuickStartREQ'
        assert schema.decode(start.name, start.payload) == {
            'boot': '2',
            'game_type': 40010101,
            'lobby_coin': 10100001,
            'byin_chips': '40',
            'wait_blind': True,
            'ip': '127.0.0.1',
        }
        await reply(socket, schema, 'pb.QuickStartRSP', {'code': 0})
        await reply(
            socket, schema, 'pb.EnterRoomRSP', {'roomid': 27, 'game_type': 40010101}
        )
        await reply(socket, schema, 'pb.CardsBRC', {'uid': 1234, 'card': 52}, 27)
        await socket.close()

    async def run() -> None:
        async with serve(server, '127.0.0.1', 0) as listener:
            port = listener.sockets[0].getsockname()[1]
            local = replace(session, server_url=f'ws://127.0.0.1:{port}')
            await observe(
                local,
                descriptors,
                tmp_path / 'capture.jsonl',
                Observation(duration=10, practice=Practice(40)),
            )

    asyncio.run(run())
    assert requests == ['pb.HeartBeatREQ', 'pb.QuickStartREQ']
    rows = [
        json.loads(line)
        for line in (tmp_path / 'capture.jsonl').read_text().splitlines()
    ]
    ready = next(row for row in rows if row['event'] == 'room-ready')
    assert ready['room_id'] == 27
    cards = next(row for row in rows if row.get('name') == 'pb.CardsBRC')
    assert cards['fields'] == {'uid': 'self', 'card': 52}


@pytest.mark.parametrize('code', [-1, 1003])
def test_rejected_login_has_no_room_requests(
    tmp_path: Path,
    descriptors: bytes,
    session: Session,
    code: int,
) -> None:
    schema = Schema(descriptors)

    async def server(socket: ServerConnection) -> None:
        assert (await receive(socket)).name == 'pb.UserLoginREQ'
        await reply(socket, schema, 'pb.UserLoginRSP', {'code': code})
        await socket.wait_closed()

    async def run() -> None:
        async with serve(server, '127.0.0.1', 0) as listener:
            port = listener.sockets[0].getsockname()[1]
            with pytest.raises(ClientError, match='rejected'):
                await observe(
                    replace(session, server_url=f'ws://127.0.0.1:{port}'),
                    descriptors,
                    tmp_path / 'capture.jsonl',
                    Observation(practice=Practice(40)),
                )

    asyncio.run(run())
    rows = [
        json.loads(line)
        for line in (tmp_path / 'capture.jsonl').read_text().splitlines()
    ]
    assert [row['name'] for row in rows if row.get('direction') == 'sent'] == [
        'pb.UserLoginREQ',
    ]
    assert rows[-1]['status'] == 'failed'


def test_passive_snapshot_and_duration(
    tmp_path: Path,
    descriptors: bytes,
    session: Session,
) -> None:
    schema = Schema(descriptors)

    async def server(socket: ServerConnection) -> None:
        await receive(socket)
        await reply(socket, schema, 'pb.UserLoginRSP', {})
        packet = await receive(socket)
        assert packet.name == 'pb.GetRoomDataREQ' and packet.room_id == 27
        assert schema.decode(packet.name, packet.payload) == {'roomid': 27}
        await reply(socket, schema, 'pb.GetRoomDataRSP', {'roomid': 27})
        await socket.wait_closed()

    async def run() -> None:
        async with serve(server, '127.0.0.1', 0) as listener:
            port = listener.sockets[0].getsockname()[1]
            await observe(
                replace(session, server_url=f'ws://127.0.0.1:{port}'),
                descriptors,
                tmp_path / 'capture.jsonl',
                Observation(duration=0.1, room_id=27),
            )

    asyncio.run(run())
    assert (
        json.loads((tmp_path / 'capture.jsonl').read_text().splitlines()[-1])['status']
        == 'duration-complete'
    )


@pytest.mark.parametrize(
    'duration,login_timeout,room_id,practice',
    [
        (0, 30, None, None),
        (float('nan'), 30, None, None),
        (float('inf'), 30, None, None),
        (60, -1, None, None),
        (60, 30, 0, None),
        (60, 30, 1, Practice(40)),
    ],
)
def test_invalid_observation_options(
    duration: float,
    login_timeout: float,
    room_id: int | None,
    practice: Practice | None,
) -> None:
    with pytest.raises(ValueError):
        Observation(duration, login_timeout, room_id, practice)


@pytest.mark.parametrize('buy_in', [39, 41, 402])
def test_invalid_training_buy_in(buy_in: int) -> None:
    with pytest.raises(ValueError):
        Practice(buy_in)


@pytest.mark.parametrize(
    'room_response',
    [
        {'code': -1},
        {'code': 0, 'roomid': 0},
        {'code': 0, 'roomid': 17},
        None,
    ],
)
def test_snapshot_rejection_or_missing_response(
    tmp_path: Path,
    descriptors: bytes,
    session: Session,
    room_response: dict[str, object] | None,
) -> None:
    schema = Schema(descriptors)

    async def server(socket: ServerConnection) -> None:
        await receive(socket)
        await reply(socket, schema, 'pb.UserLoginRSP', {})
        assert (await receive(socket)).name == 'pb.GetRoomDataREQ'
        if room_response is not None:
            await reply(socket, schema, 'pb.GetRoomDataRSP', room_response)
        else:
            await reply(socket, schema, 'pb.EnterRoomRSP', {'roomid': 17})

        await socket.close()

    async def run() -> None:
        async with serve(server, '127.0.0.1', 0) as listener:
            port = listener.sockets[0].getsockname()[1]
            with pytest.raises(ClientError):
                await observe(
                    replace(session, server_url=f'ws://127.0.0.1:{port}'),
                    descriptors,
                    tmp_path / 'capture.jsonl',
                    Observation(room_id=27),
                )

    asyncio.run(run())
    assert (
        json.loads((tmp_path / 'capture.jsonl').read_text().splitlines()[-1])['status']
        == 'failed'
    )
