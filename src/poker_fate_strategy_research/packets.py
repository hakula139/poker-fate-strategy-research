import re
import struct
from dataclasses import dataclass


_HEADER = struct.Struct('>IH')
_ROOM = struct.Struct('>I')
_NAME = re.compile(r'pb\.[A-Za-z_][A-Za-z0-9_]*\Z')


@dataclass(frozen=True)
class Packet:
    name: str
    room_id: int
    payload: bytes


def pack(packet: Packet) -> bytes:
    if not _NAME.fullmatch(packet.name):
        raise ValueError('Invalid protocol name.')

    name = packet.name.encode('utf-8')
    length = 2 + len(name) + 4 + len(packet.payload)
    return (
        _HEADER.pack(length, len(name))
        + name
        + _ROOM.pack(packet.room_id)
        + packet.payload
    )


def unpack(frame: bytes) -> list[Packet]:
    packets = []
    offset = 0
    while offset < len(frame):
        if len(frame) - offset < _HEADER.size:
            raise ValueError('Truncated packet header.')

        length, name_length = _HEADER.unpack_from(frame, offset)
        end = offset + 4 + length
        if length < 2 + name_length + 4 or end > len(frame):
            raise ValueError('Invalid packet length.')

        name_start = offset + _HEADER.size
        name_end = name_start + name_length
        name = frame[name_start:name_end].decode('utf-8')
        if not _NAME.fullmatch(name):
            raise ValueError('Invalid protocol name.')

        room_id = _ROOM.unpack_from(frame, name_end)[0]
        packets.append(Packet(name, room_id, frame[name_end + 4 : end]))
        offset = end

    if not packets:
        raise ValueError('Empty protocol frame.')

    return packets
