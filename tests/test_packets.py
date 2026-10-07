import struct

import pytest

from poker_fate_strategy_research.packets import Packet, pack, unpack


def test_packet_round_trip_and_multiple_packets() -> None:
    login = Packet('pb.UserLoginREQ', 0, b'\x08\x01')
    room = Packet('pb.GetCardsRSP', 4294967295, b'\x0a\x02\x01\x02')
    frame = pack(login) + pack(room)
    assert frame[:6] == struct.pack('>IH', 2 + len(login.name) + 4 + 2, len(login.name))
    assert unpack(frame) == [login, room]


@pytest.mark.parametrize(
    'frame',
    [
        b'',
        b'\x00',
        struct.pack('>IH', 4, 1) + b'x',
        struct.pack('>IH', 100, 1) + b'x' + bytes(4),
        struct.pack('>IH', 7, 1) + b'\xff' + bytes(4),
        struct.pack('>IH', 7, 1) + b'x' + bytes(4),
        pack(Packet('pb.Test', 1, b'')) + b'\x00',
    ],
)
def test_reject_malformed_frame(frame: bytes) -> None:
    with pytest.raises(ValueError):
        unpack(frame)


def test_reject_invalid_outgoing_name() -> None:
    with pytest.raises(ValueError):
        pack(Packet('pb.Invalid\nname', 0, b''))
