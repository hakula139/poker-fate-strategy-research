from __future__ import annotations

import argparse
import hmac
import importlib
import json
import math
import secrets
import threading
import time
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Self

from google.protobuf.message import DecodeError

from .errors import InputError
from .local_files import private_output
from .packets import unpack
from .schema import Schema


_MESSAGES = {
    'pb.ActionBRC',
    'pb.ActionNotifyBRC',
    'pb.AnteBRC',
    'pb.ChangeObserveViewRSP',
    'pb.ChangeTableRSP',
    'pb.DealerInfoRSP',
    'pb.EnterRoomRSP',
    'pb.GetCardsRSP',
    'pb.GetHandsListRSP',
    'pb.GetRoomDataRSP',
    'pb.HandCardRSP',
    'pb.RoundOverBRC',
    'pb.RoundStartBRC',
    'pb.ShowHandRSP',
    'pb.ShowMyCardBRC',
    'pb.SitDownBRC',
    'pb.WinnerRSP',
}
_NUMBERS = {
    'action_chips',
    'action_idx',
    'action_seatid',
    'action_type',
    'bb_idx',
    'begin_chips',
    'big_blind',
    'board',
    'board_cards',
    'call_need_chips',
    'card1',
    'card2',
    'card3',
    'card4',
    'cards',
    'chips',
    'code',
    'd_idx',
    'dealer',
    'destop_chips',
    'hand_cards',
    'hand_chips',
    'hand_type',
    'has_card',
    'id',
    'is_allin',
    'is_fold',
    'is_playing',
    'is_show_card',
    'last_action_type',
    'left_hand_chips',
    'max_chipin',
    'min_chipin',
    'pool',
    'poolid',
    'pot',
    'sb_idx',
    'seatid',
    'seatid_being_observed',
    'show_card_info',
    'show_type_list',
    'small_blind',
    'stage',
}
_CONTAINERS = {
    'action',
    'ante',
    'hands',
    'his_detail',
    'info',
    'items',
    'playing_status',
    'pool_rd',
    'profit',
    'round_rd',
    'seat',
    'show_round_rd',
    'start_info',
    'status',
    'table_status',
    'users',
    'winner',
}


def gameplay_fields(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in _NUMBERS:
            if isinstance(item, list):
                result[key] = [
                    number for child in item if (number := _number(child)) is not None
                ]
            elif (number := _number(item)) is not None:
                result[key] = number
        elif key in _CONTAINERS:
            if isinstance(item, dict):
                result[key] = gameplay_fields(item)
            elif isinstance(item, list):
                result[key] = [
                    gameplay_fields(child) for child in item if isinstance(child, dict)
                ]
    return result


def _number(value: Any) -> int | bool | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.removeprefix('-').isdigit():
        return int(value)
    return None


class ReceiveCapture:
    def __init__(self, path: Path, schema: Schema) -> None:
        self.stream = private_output(path)
        self.schema = schema
        self.sequence = 0
        self.observed_deal_sequence = 0
        self.hand_card_seat: int | None = None
        self.hand_salt = secrets.token_bytes(32)
        self.lock = threading.Lock()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.stream.close()

    def frame(self, data: bytes, frame_sequence: int, observed_at_ms: int) -> None:
        with self.lock:
            try:
                packets = unpack(data)
            except (ValueError, UnicodeError):
                self._write(
                    {'event': 'invalid-frame', 'frame_sequence': frame_sequence}
                )
                return
            for packet in packets:
                self.sequence += 1
                record: dict[str, Any] = {
                    'event': 'packet',
                    'sequence': self.sequence,
                    'frame_sequence': frame_sequence,
                    'observed_at': datetime.fromtimestamp(
                        observed_at_ms / 1000, UTC
                    ).isoformat(),
                    'recipient': 'self',
                    'name': packet.name,
                    'payload_size': len(packet.payload),
                }
                if packet.name == 'pb.DealerInfoRSP':
                    self.observed_deal_sequence += 1
                if packet.name in {'pb.ChangeTableRSP', 'pb.EnterRoomRSP'}:
                    self.hand_card_seat = None
                record['observed_deal_sequence'] = self.observed_deal_sequence
                if packet.name in {'pb.UserLoginREQ', 'pb.UserLoginRSP'}:
                    record['decode_status'] = 'authentication-omitted'
                elif packet.name not in _MESSAGES:
                    record['decode_status'] = 'metadata-only'
                else:
                    try:
                        decoded = self.schema.inspect(packet.name, packet.payload)
                        record['fields'] = gameplay_fields(decoded.fields)
                        hand_fields = decoded.fields
                        if packet.name == 'pb.GetHandsListRSP':
                            hand_fields = decoded.fields.get('info', {})
                        elif 'table_status' in decoded.fields:
                            hand_fields = decoded.fields['table_status']
                        game_id = hand_fields.get('gameid')
                        if isinstance(game_id, str) and game_id:
                            record['packet_hand_reference'] = hmac.new(
                                self.hand_salt, game_id.encode(), 'sha256'
                            ).hexdigest()
                        if packet.name == 'pb.HandCardRSP':
                            seat = decoded.fields.get('seatid')
                            if isinstance(seat, int):
                                self.hand_card_seat = seat
                        elif (
                            packet.name == 'pb.ChangeObserveViewRSP'
                            and decoded.fields.get('code', 0) == 0
                        ):
                            self.hand_card_seat = None
                        record['unknown_fields'] = decoded.unknown_fields
                        record['decode_status'] = 'decoded'
                    except KeyError:
                        record['decode_status'] = 'unknown-message'
                    except DecodeError:
                        record['decode_status'] = 'invalid-protobuf'
                record['last_hand_card_seat'] = self.hand_card_seat
                self._write(record)

    def _write(self, record: dict[str, Any]) -> None:
        record['recorded_at'] = datetime.now(UTC).isoformat()
        record['monotonic_ns'] = time.monotonic_ns()
        self.stream.write(json.dumps(record) + '\n')
        self.stream.flush()


def add_android_command(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = commands.add_parser(
        'observe-android',
        help='Read received packets from the official Android 1.7.0 client.',
    )
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=60)
    parser.set_defaults(run=_observe)


def _observe(args: argparse.Namespace) -> None:
    if args.pid <= 0 or not math.isfinite(args.duration) or args.duration <= 0:
        raise InputError('PID and duration must be positive.')
    try:
        frida = importlib.import_module('frida')
    except ImportError as error:
        raise InputError('Install the Android extra to use this command.') from error

    schema = Schema(args.schema.read_bytes())
    stopped = threading.Event()
    ready = threading.Event()
    failed = threading.Event()
    failed_stage = 'process or artifact'
    device = frida.get_device('emulator-5554', timeout=10)
    application = next(
        (
            item
            for item in device.enumerate_applications()
            if item.identifier == 'com.pokerfate.play' and item.pid == args.pid
        ),
        None,
    )
    if application is None:
        raise InputError('PID must identify the official game on emulator-5554.')
    session = device.attach(args.pid)
    try:
        session.on('detached', lambda *_: stopped.set())
        with ReceiveCapture(args.output, schema) as capture:

            def on_message(message: dict[str, Any], data: bytes | None) -> None:
                nonlocal failed_stage
                if message.get('type') != 'send':
                    failed.set()
                    stopped.set()
                    return
                payload = message.get('payload')
                if not isinstance(payload, dict):
                    failed.set()
                    stopped.set()
                    return
                event = payload.get('event')
                stage = payload.get('stage')
                if event == 'setup-error' and stage in {
                    'architecture',
                    'attach',
                    'library-hash',
                    'library-read',
                    'module',
                    'receive-address',
                }:
                    failed_stage = stage
                if event == 'ready':
                    ready.set()
                elif event == 'frame' and data is not None:
                    try:
                        capture.frame(
                            data, payload['sequence'], payload['observed_at_ms']
                        )
                    except Exception:
                        failed.set()
                        stopped.set()
                else:
                    failed.set()
                    stopped.set()

            source = (
                files('poker_fate_strategy_research')
                .joinpath('android/receive.js')
                .read_text()
            )
            script = session.create_script(source)
            script.on('message', on_message)
            script.load()
            try:
                deadline = time.monotonic() + 15
                while not ready.is_set() and not stopped.is_set():
                    if time.monotonic() >= deadline:
                        raise InputError('Receive observer did not become ready.')
                    stopped.wait(0.1)
                if failed.is_set():
                    raise InputError(f'Receive observer rejected the {failed_stage}.')
                if not ready.is_set():
                    raise InputError(
                        'Game process detached before the observer was ready.'
                    )
                print(
                    'Receive observer attached. Raw payloads remain in memory.',
                    flush=True,
                )
                stopped.wait(args.duration)
                if failed.is_set():
                    raise InputError(
                        'Receive observer stopped after an instrumentation error.'
                    )
            finally:
                script.unload()
    finally:
        session.detach()
    print('Receive observer detached.', flush=True)
