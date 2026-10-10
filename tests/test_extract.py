import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import BadZipFile, ZipFile

import pytest
import UnityPy

from poker_fate_strategy_research import extract
from poker_fate_strategy_research.extract import extract_apk


def _asset_pointer(
    name: str, data: bytes, path_id: int, encoded: int
) -> SimpleNamespace:
    obj = SimpleNamespace(
        type=SimpleNamespace(name='MonoBehaviour'),
        path_id=path_id,
        parse_as_dict=lambda: {'m_Name': name, 'data': data, 'encode': encoded},
    )
    return SimpleNamespace(deref=lambda: obj)


def test_extract_apk_preserves_sources_and_records_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apk = tmp_path / 'client.apk'
    metadata = b'prefix' + bytes(value ^ 0x3D for value in range(8))
    lua_entry = 'assets/aa/Android/gameres_assets_src/app/example.bundle'
    proto_entry = 'assets/aa/Android/gameres_assets_proto_example.bundle'
    with ZipFile(apk, 'w') as archive:
        archive.writestr(
            'assets/bin/Data/Managed/Metadata/global-metadata.dat', metadata
        )
        archive.writestr(lua_entry, b'wrapped lua')
        archive.writestr(proto_entry, b'wrapped proto')
        archive.writestr('assets/aa/Android/unrelated.bundle', b'ignore me')

    def unwrap(data: bytes, seed: int) -> bytes:
        assert seed == int.from_bytes(bytes(range(8)), 'little')
        return b'UnityFS\0' + data

    lua = SimpleNamespace(
        container={
            'src/engine/init.lua': _asset_pointer(
                'init',
                bytes.fromhex('8d301105c26b748133747aa67855f72424228fe71d0232b9'),
                11,
                1,
            ),
            'src/ui/init.lua': _asset_pointer('init', b'return "ui"', 12, 0),
        }
    )
    proto = SimpleNamespace(
        container={
            'proto/Example.proto': _asset_pointer(
                'Example',
                bytes.fromhex(
                    '8d074d7e764e9cdc3ca35cabbd866c406bad8a1400da39967b59c5d464d121023'
                    '34dffd3f37217fae92dded2206fd0b839b6f7c5'
                ),
                21,
                1,
            )
        }
    )
    environments = {b'UnityFS\0wrapped lua': lua, b'UnityFS\0wrapped proto': proto}
    monkeypatch.setattr(extract, 'unwrap_bundle', unwrap)
    monkeypatch.setattr(UnityPy, 'load', environments.__getitem__)

    expected = {
        'sources/example/src/engine/init.lua': b'return {value = 42}',
        'sources/example/src/ui/init.lua': b'return "ui"',
        'sources/gameres_assets_proto_example/proto/Example.proto': (
            b'message Example { optional uint32 value = 1; }'
        ),
    }

    output = tmp_path / 'decoded'
    assert extract_apk(apk, output, 6) == 3

    inventory = json.loads((output / 'inventory.json').read_text())
    assert inventory['apk_sha256'] == hashlib.sha256(apk.read_bytes()).hexdigest()
    assert inventory['metadata_sha256'] == hashlib.sha256(metadata).hexdigest()
    assert inventory['seed_offset'] == 6
    assert [bundle['apk_entry'] for bundle in inventory['bundles']] == [
        lua_entry,
        proto_entry,
    ]
    for bundle in inventory['bundles']:
        wrapped = (
            b'wrapped proto' if bundle['apk_entry'] == proto_entry else b'wrapped lua'
        )
        assert bundle['wrapped_sha256'] == hashlib.sha256(wrapped).hexdigest()
        assert (
            bundle['unwrapped_sha256']
            == hashlib.sha256(b'UnityFS\0' + wrapped).hexdigest()
        )

    identities = {
        'src/engine/init.lua': ('init', 11, 1),
        'src/ui/init.lua': ('init', 12, 0),
        'proto/Example.proto': ('Example', 21, 1),
    }
    assets = [asset for bundle in inventory['bundles'] for asset in bundle['assets']]
    assert {asset['path'] for asset in assets} == expected.keys()
    for asset in assets:
        assert type(asset['encoded']) is int
        assert (asset['name'], asset['path_id'], asset['encoded']) == identities[
            asset['container_path']
        ]
        data = expected[asset['path']]
        assert (output / asset['path']).read_bytes() == data
        assert asset['size'] == len(data)
        assert asset['sha256'] == hashlib.sha256(data).hexdigest()

    with pytest.raises(FileExistsError):
        extract_apk(apk, output, 6)
    assert (output / 'sources/example/src/ui/init.lua').read_bytes() == b'return "ui"'


@pytest.mark.parametrize(
    'invalid_input', ['missing', 'archive', 'metadata', 'seed', 'sources']
)
def test_invalid_apk_does_not_reserve_output(
    tmp_path: Path, invalid_input: str
) -> None:
    apk = tmp_path / 'client.apk'
    if invalid_input == 'archive':
        apk.write_bytes(b'not an APK')
    elif invalid_input in {'metadata', 'seed', 'sources'}:
        with ZipFile(apk, 'w') as archive:
            if invalid_input in {'seed', 'sources'}:
                archive.writestr(
                    'assets/bin/Data/Managed/Metadata/global-metadata.dat',
                    b'short' if invalid_input == 'seed' else bytes(14),
                )

    output = tmp_path / 'decoded'
    with pytest.raises((OSError, BadZipFile, KeyError, ValueError)):
        extract_apk(apk, output, 6)

    assert not output.exists()
