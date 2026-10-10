import argparse
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet

from poker_fate_strategy_research.android_observer import (
    ReceiveCapture,
    _observe,
    gameplay_fields,
)
from poker_fate_strategy_research.errors import InputError
from poker_fate_strategy_research.packets import Packet, pack
from poker_fate_strategy_research.schema import Schema


def test_allowlist_removes_identity_and_unexpected_strings() -> None:
    fields = gameplay_fields(
        {
            'table_status': {
                'stage': 2,
                'board': [1, '2', 'private-token'],
                'seat': [
                    {
                        'seatid': 3,
                        'card1': 14,
                        'uid': '12345',
                        'player': {'nick': 'Identifiable Player'},
                        'token': 'private-token',
                        'hand_chips': '9007199254740993',
                    }
                ],
                'gameid': 'identifiable-game',
                'new_field': {'card1': 52},
            },
            'card1': 'private-token',
            'info': [{'hand_cards': [0, 25], 'name': 'Identifiable Player'}],
        }
    )
    assert fields == {
        'table_status': {
            'stage': 2,
            'board': [1, 2],
            'seat': [{'seatid': 3, 'card1': 14, 'hand_chips': 9007199254740993}],
        },
        'info': [{'hand_cards': [0, 25]}],
    }


def test_capture_omits_auth_and_preserves_receive_order(
    tmp_path: Path, descriptors: bytes
) -> None:
    path = tmp_path / 'receive.jsonl'
    file = FileDescriptorProto(name='cards.proto', package='pb', syntax='proto2')
    for name in ('DealerInfoRSP', 'HandCardRSP', 'RoundStartBRC'):
        message = file.message_type.add(name=name)
        message.field.add(name='card1', number=1, type=5, label=1)
        message.field.add(name='token', number=2, type=9, label=1)
        message.field.add(name='seatid', number=3, type=5, label=1)
    base = FileDescriptorSet.FromString(descriptors)
    base.file.append(file)
    schema = Schema(base.SerializeToString())
    with ReceiveCapture(path, schema) as capture:
        capture.frame(
            pack(Packet('pb.UserLoginRSP', 0, b'private-token'))
            + pack(Packet('pb.DealerInfoRSP', 9, b''))
            + pack(
                Packet(
                    'pb.HandCardRSP',
                    9,
                    schema.encode(
                        'pb.HandCardRSP',
                        {'card1': 42, 'seatid': 3, 'token': 'private-token'},
                    )
                    + b'\x20\x01',
                )
            ),
            1,
            1000,
        )
        capture.frame(pack(Packet('pb.OtherRSP', 9, b'private-token')), 2, 1100)
        capture.frame(pack(Packet('pb.RoundStartBRC', 9, b'\x0a\x10')), 3, 1200)
        capture.frame(b'private-token', 4, 1300)
    text = path.read_text()
    assert 'private-token' not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[0]['decode_status'] == 'authentication-omitted'
    assert 'fields' not in rows[0]
    assert rows[2]['fields'] == {'card1': 42, 'seatid': 3}
    assert rows[0]['last_hand_card_seat'] is None
    assert rows[2]['last_hand_card_seat'] == 3
    assert rows[3]['last_hand_card_seat'] == 3
    assert rows[2]['unknown_fields'] is True
    assert [row['sequence'] for row in rows[:-1]] == [1, 2, 3, 4, 5]
    assert [row['observed_deal_sequence'] for row in rows[:3]] == [0, 1, 1]
    assert all(row['recipient'] == 'self' for row in rows[:-1])
    assert rows[2]['frame_sequence'] == 1
    assert rows[2]['observed_at'] == '1970-01-01T00:00:01+00:00'
    assert rows[3]['decode_status'] == 'metadata-only'
    assert rows[4]['decode_status'] == 'invalid-protobuf'
    assert rows[5]['event'] == 'invalid-frame'
    assert path.stat().st_mode & 0o777 == 0o600


def test_history_cards_preserve_seats_without_player_identity() -> None:
    assert gameplay_fields(
        {
            'code': 0,
            'info': {
                'id': 42,
                'gameid': 'private-game-id',
                'board': [1, 2, 3],
                'hands': [
                    {
                        'brief': {'uid': '123', 'name': 'Identifiable Player'},
                        'cards': [15, 29],
                        'is_fold': True,
                        'hand_type': 2,
                        'seatid': 4,
                    }
                ],
            },
        }
    ) == {
        'code': 0,
        'info': {
            'id': 42,
            'board': [1, 2, 3],
            'hands': [
                {'cards': [15, 29], 'is_fold': True, 'hand_type': 2, 'seatid': 4}
            ],
        },
    }


def test_sit_down_capture_retains_cards_without_identity(tmp_path: Path) -> None:
    file = FileDescriptorProto(name='seats.proto', package='pb', syntax='proto2')
    player = file.message_type.add(name='UserBrief')
    player.field.add(name='uid', number=1, type=3, label=1)
    player.field.add(name='name', number=2, type=9, label=1)
    status = file.message_type.add(name='SeatStatus')
    status.field.add(name='seatid', number=1, type=5, label=1)
    status.field.add(
        name='player', number=3, type=11, type_name='.pb.UserBrief', label=1
    )
    status.field.add(name='hand_chips', number=4, type=3, label=1)
    for number, name in enumerate(('card1', 'card2', 'card3', 'card4'), start=18):
        status.field.add(name=name, number=number, type=5, label=1)
    message = file.message_type.add(name='SitDownBRC')
    message.field.add(
        name='status', number=4, type=11, type_name='.pb.SeatStatus', label=1
    )
    message.field.add(name='token', number=5, type=9, label=1)
    schema = Schema(FileDescriptorSet(file=[file]).SerializeToString())
    payload = schema.encode(
        'pb.SitDownBRC',
        {
            'status': {
                'seatid': 3,
                'player': {'uid': 123456789, 'name': 'Identifiable Player'},
                'hand_chips': 200,
                'card1': 15,
                'card2': 29,
                'card3': 0,
                'card4': 0,
            },
            'token': 'private-token',
        },
    )
    output = tmp_path / 'seats.jsonl'
    with ReceiveCapture(output, schema) as capture:
        capture.frame(pack(Packet('pb.SitDownBRC', 9, payload)), 1, 1000)
    text = output.read_text()
    row = json.loads(text)
    assert row['decode_status'] == 'decoded'
    assert row['fields'] == {
        'status': {
            'seatid': 3,
            'hand_chips': 200,
            'card1': 15,
            'card2': 29,
            'card3': 0,
            'card4': 0,
        }
    }
    assert row['last_hand_card_seat'] is None
    assert all(
        value not in text
        for value in ('123456789', 'Identifiable Player', 'private-token')
    )


def test_observer_detaches_on_script_failure(
    tmp_path: Path, descriptors: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    class Script:
        callback: Any

        def on(self, name: str, callback: Any) -> None:
            self.callback = callback

        def load(self) -> None:
            self.callback({'type': 'error', 'stack': 'private-token'}, None)

        def unload(self) -> None:
            events.append('unload')

    class Session:
        def on(self, name: str, callback: Any) -> None:
            pass

        def create_script(self, source: str) -> Script:
            return Script()

        def detach(self) -> None:
            events.append('detach')

    class Device:
        def enumerate_applications(self) -> list[Any]:
            return [SimpleNamespace(pid=123, identifier='com.pokerfate.play')]

        def attach(self, pid: int) -> Session:
            events.append('attach')
            return Session()

    def get_device(identifier: str, timeout: int) -> Device:
        assert identifier == 'emulator-5554'
        return Device()

    original_import = importlib.import_module
    monkeypatch.setattr(
        'poker_fate_strategy_research.android_observer.importlib.import_module',
        lambda name: (
            SimpleNamespace(get_device=get_device)
            if name == 'frida'
            else original_import(name)
        ),
    )
    schema_path = tmp_path / 'schema.pb'
    schema_path.write_bytes(descriptors)
    output = tmp_path / 'receive.jsonl'
    with pytest.raises(InputError, match='rejected the process or artifact'):
        _observe(
            argparse.Namespace(pid=123, schema=schema_path, output=output, duration=1)
        )
    assert events == ['attach', 'unload', 'detach']
    assert output.read_text() == ''


def test_history_hand_reference_is_independent_of_latest_deal(tmp_path: Path) -> None:
    file = FileDescriptorProto(name='history.proto', package='pb', syntax='proto2')
    for name in ('DealerInfoRSP', 'HandsInfo'):
        message = file.message_type.add(name=name)
        message.field.add(name='gameid', number=1, type=9, label=1)
    message = file.message_type.add(name='GetHandsListRSP')
    message.field.add(
        name='info', number=1, type=11, type_name='.pb.HandsInfo', label=1
    )
    schema = Schema(FileDescriptorSet(file=[file]).SerializeToString())
    output = tmp_path / 'history.jsonl'
    messages: list[tuple[str, dict[str, Any]]] = [
        ('pb.DealerInfoRSP', {'gameid': 'private-old-hand'}),
        ('pb.DealerInfoRSP', {'gameid': 'private-current-hand'}),
        ('pb.GetHandsListRSP', {'info': {'gameid': 'private-old-hand'}}),
    ]
    with ReceiveCapture(output, schema) as capture:
        for sequence, (name, fields) in enumerate(
            messages,
            start=1,
        ):
            capture.frame(
                pack(Packet(name, 1, schema.encode(name, fields))), sequence, 1000
            )
    text = output.read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert 'private-old-hand' not in text and 'private-current-hand' not in text
    assert rows[2]['observed_deal_sequence'] == 2
    assert rows[2]['packet_hand_reference'] == rows[0]['packet_hand_reference']
    assert rows[2]['packet_hand_reference'] != rows[1]['packet_hand_reference']


def test_hand_card_owners_do_not_define_recipient_identity(tmp_path: Path) -> None:
    file = FileDescriptorProto(name='owners.proto', package='pb', syntax='proto2')
    message = file.message_type.add(name='HandCardRSP')
    message.field.add(name='seatid', number=1, type=5, label=1)
    message.field.add(name='card1', number=2, type=5, label=1)
    schema = Schema(FileDescriptorSet(file=[file]).SerializeToString())
    output = tmp_path / 'owners.jsonl'
    with ReceiveCapture(output, schema) as capture:
        for seat in (1, 2):
            payload = schema.encode(
                'pb.HandCardRSP', {'seatid': seat, 'card1': 14 + seat}
            )
            capture.frame(pack(Packet('pb.HandCardRSP', 9, payload)), seat, 1000)
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row['fields']['seatid'] for row in rows] == [1, 2]
    assert [row['last_hand_card_seat'] for row in rows] == [1, 2]
    assert all(row['recipient'] == 'self' for row in rows)
    assert all('self_seat' not in row for row in rows)


def test_observer_view_switch_retains_cards_and_clears_owner_context(
    tmp_path: Path,
) -> None:
    file = FileDescriptorProto(name='views.proto', package='pb', syntax='proto2')
    status = file.message_type.add(name='PlayingStatus')
    status.field.add(name='card1', number=1, type=5, label=1)
    status.field.add(name='uid', number=2, type=3, label=1)
    hand = file.message_type.add(name='HandCardRSP')
    hand.field.add(name='seatid', number=1, type=5, label=1)
    switch = file.message_type.add(name='ChangeObserveViewRSP')
    switch.field.add(name='code', number=1, type=5, label=1)
    switch.field.add(name='seatid_being_observed', number=3, type=5, label=1)
    switch.field.add(
        name='playing_status', number=4, type=11, type_name='.pb.PlayingStatus', label=1
    )
    schema = Schema(FileDescriptorSet(file=[file]).SerializeToString())
    output = tmp_path / 'views.jsonl'
    messages: list[tuple[str, dict[str, Any]]] = [
        ('pb.HandCardRSP', {'seatid': 1}),
        ('pb.ChangeObserveViewRSP', {'code': 1, 'seatid_being_observed': 2}),
        (
            'pb.ChangeObserveViewRSP',
            {
                'code': 0,
                'seatid_being_observed': 3,
                'playing_status': {'card1': 42, 'uid': 123456789},
            },
        ),
    ]
    with ReceiveCapture(output, schema) as capture:
        for sequence, (name, fields) in enumerate(messages, start=1):
            payload = schema.encode(name, fields)
            capture.frame(pack(Packet(name, 9, payload)), sequence, 1000)
    text = output.read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[1]['last_hand_card_seat'] == 1
    assert rows[2]['last_hand_card_seat'] is None
    assert rows[2]['fields'] == {
        'code': 0,
        'seatid_being_observed': 3,
        'playing_status': {'card1': 42},
    }
    assert rows[2]['decode_status'] == 'decoded'
    assert rows[2]['recipient'] == 'self'
    assert '123456789' not in text
