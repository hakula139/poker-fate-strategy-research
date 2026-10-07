import struct

import xxtea


_MASK = (1 << 64) - 1
_LUA_KEY = b'bee#happy&pkproject'[:16]
_PROTO_KEY = b'bee#happy&pkproto'[:16]


def seed_from_metadata(metadata: bytes, field_offset: int) -> int:
    if field_offset < 0 or field_offset + 8 > len(metadata):
        raise ValueError('Seed field is outside the metadata file')
    field = metadata[field_offset : field_offset + 8]
    return int.from_bytes(bytes(value ^ 0x3D for value in field), 'little')


def unwrap_bundle(data: bytes, secret_seed: int) -> bytes:
    if not data.startswith(b'XENC') or len(data) < 20:
        raise ValueError('Expected a complete XENC header')

    left, right = struct.unpack_from('<QQ', data, 4)
    mixed = left ^ right
    mixed = ((mixed ^ (mixed >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
    mixed = ((mixed ^ (mixed >> 27)) * 0x94D049BB133111EB) & _MASK
    seed = (mixed ^ (mixed >> 31)) ^ secret_seed

    payload = bytearray(data[20:])
    for block in range(0, len(payload), 64):
        state = (seed + (block // 64) * 0x9E3779B97F4A7C15) & _MASK
        for index in range(block, min(block + 64, len(payload))):
            state ^= (state << 13) & _MASK
            state ^= state >> 7
            state ^= (state << 17) & _MASK
            payload[index] ^= state & 0xFF

    if not payload.startswith(b'UnityFS\x00'):
        raise ValueError('Decoded bundle does not have a UnityFS header')
    return bytes(payload)


def decode_asset(data: bytes, *, proto: bool) -> bytes:
    if len(data) < 8 or len(data) % 4:
        raise ValueError('Expected complete XXTEA ciphertext words')

    key = _PROTO_KEY if proto else _LUA_KEY
    decoded: bytes = xxtea.decrypt(data, key, padding=False)
    length = struct.unpack_from('<I', decoded, len(decoded) - 4)[0]
    if not len(decoded) - 7 <= length <= len(decoded) - 4:
        raise ValueError('Invalid XXTEA payload length')
    return decoded[:length]
