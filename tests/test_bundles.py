import pytest

from poker_fate_strategy_research.bundles import (
    decode_asset,
    seed_from_metadata,
    unwrap_bundle,
)


_WRAPPED = bytes.fromhex(
    '58454e43000102030405060708090a0b0c0d0e0f'
    '2bd8aa8eb4fcaa40b442612ad1b7ed29d2b4da8c40f1c3d979d0b4fc608f7956'
    '3558b777eac06adfaf99b5cf4d9c9e98540b36a50d8cf6e46081b9ffb37d600b1'
    '3c2dc4ae56fb032cf15546152f7fd5b2e390825cea0cea4486b565d4869ee44cfa'
    'bd7edbf39fa52196acffbeb8383a9b14d24651eb5f56532a7d97f34ddb7ed616ec'
    'faf43c2ec42157b'
)


def test_seed_from_metadata_reads_the_selected_field() -> None:
    field = bytes(value ^ 0x3D for value in bytes.fromhex('0807060504030201'))
    assert seed_from_metadata(b'prefix' + field + b'suffix', 6) == 0x0102030405060708


@pytest.mark.parametrize('offset', [-1, 1])
def test_seed_from_metadata_rejects_out_of_bounds_field(offset: int) -> None:
    with pytest.raises(ValueError, match='outside the metadata'):
        seed_from_metadata(b'12345678', offset)


def test_unwrap_bundle_crosses_multiple_keystream_blocks() -> None:
    assert unwrap_bundle(_WRAPPED, 0x0102030405060708) == b'UnityFS\x00' + bytes(
        range(130)
    )


@pytest.mark.parametrize('wrapped', [b'UnityFS\x00', b'XENC' + bytes(15)])
def test_unwrap_bundle_rejects_invalid_headers(wrapped: bytes) -> None:
    with pytest.raises(ValueError, match='complete XENC header'):
        unwrap_bundle(wrapped, 0)


def test_unwrap_bundle_rejects_a_mismatched_seed() -> None:
    with pytest.raises(ValueError, match='UnityFS header'):
        unwrap_bundle(_WRAPPED, 0)


@pytest.mark.parametrize(
    ('ciphertext', 'proto', 'expected'),
    [
        (
            '8d301105c26b748133747aa67855f72424228fe71d0232b9',
            False,
            b'return {value = 42}',
        ),
        (
            '8d074d7e764e9cdc3ca35cabbd866c406bad8a1400da39967b59c5d464d121023'
            '34dffd3f37217fae92dded2206fd0b839b6f7c5',
            True,
            b'message Example { optional uint32 value = 1; }',
        ),
    ],
)
def test_decode_asset_selects_key_and_removes_length_padding(
    ciphertext: str, proto: bool, expected: bytes
) -> None:
    assert decode_asset(bytes.fromhex(ciphertext), proto=proto) == expected


def test_decode_asset_rejects_invalid_embedded_length() -> None:
    with pytest.raises(ValueError, match='Invalid XXTEA payload length'):
        decode_asset(bytes.fromhex('576d735291c1274c'), proto=False)


@pytest.mark.parametrize('ciphertext', [b'', b'1234', b'123456789'])
def test_decode_asset_rejects_incomplete_words(ciphertext: bytes) -> None:
    with pytest.raises(ValueError, match='complete XXTEA ciphertext'):
        decode_asset(ciphertext, proto=False)
