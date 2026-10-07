import json
from dataclasses import replace
from pathlib import Path

from poker_fate_strategy_research.capture import Capture
from poker_fate_strategy_research.packets import Packet
from poker_fate_strategy_research.schema import Schema
from poker_fate_strategy_research.session import Session


def test_capture_presence_identity_and_redaction(
    tmp_path: Path,
    descriptors: bytes,
    session: Session,
) -> None:
    path = tmp_path / 'capture.jsonl'
    schema = Schema(descriptors)
    with Capture(path, schema, session) as capture:
        for uid in (1234, 9999, 9999):
            packet = Packet(
                'pb.CardsBRC',
                27,
                schema.encode(
                    'pb.CardsBRC',
                    {
                        'uid': uid,
                        'card': 52,
                        'key': session.rdkey,
                    },
                ),
            )
            capture.packet(packet, 'received', '2026-10-07T00:00:00+00:00', 120)

        capture.packet(
            Packet('pb.UserLoginREQ', 0, b'synthetic-session-key'),
            'sent',
            '2026-10-07T00:00:00+00:00',
            121,
        )
        capture.packet(
            Packet('pb.UnknownBRC', 27, b'synthetic-session-key'),
            'received',
            '2026-10-07T00:00:00+00:00',
            122,
        )
        capture.packet(
            Packet('pb.CardsBRC', 27, b'\x0a\x10'),
            'received',
            '2026-10-07T00:00:00+00:00',
            123,
        )
        capture.event('test', detail=f'key: {session.rdkey}', token='private')

    text = path.read_text()
    assert session.rdkey not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[0]['fields'] == {'uid': 'self', 'card': 52, 'key': '[redacted]'}
    assert rows[1]['fields']['uid'] == rows[2]['fields']['uid']
    assert rows[1]['fields']['uid'].startswith('player-')
    assert rows[0]['room_id'] == 27 and rows[0]['monotonic_ns'] == 120
    assert rows[3]['decode_status'] == 'authentication-omitted'
    assert 'payload_sha256' not in rows[3] and 'fields' not in rows[3]
    assert rows[4]['decode_status'] == 'unknown-message'
    assert rows[5]['decode_status'] == 'invalid-protobuf'
    assert rows[6]['token'] == '[redacted]'

    other = tmp_path / 'other.jsonl'
    with Capture(other, schema, replace(session, uid=8888)) as capture:
        assert capture.redact(9999, 'uid') != rows[1]['fields']['uid']
