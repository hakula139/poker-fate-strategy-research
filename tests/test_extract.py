import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
import UnityPy

from poker_fate_strategy_research import extract
from poker_fate_strategy_research.extract import asset_path, extract_apk


def test_asset_path_preserves_distinct_container_paths(tmp_path: Path) -> None:
    engine = asset_path(tmp_path, 'src/engine/init.lua')
    interface = asset_path(tmp_path, 'src/ui/init.lua')
    assert engine == tmp_path / 'src/engine/init.lua'
    assert interface == tmp_path / 'src/ui/init.lua'
    assert engine != interface


@pytest.mark.parametrize(
    'name', ['/absolute.lua', '../outside.lua', 'src/../../out', '.']
)
def test_asset_path_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match='Unsafe asset name'):
        asset_path(tmp_path, name)


def test_asset_path_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / 'sources'
    root.mkdir()
    (root / 'linked').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes output directory'):
        asset_path(root, 'linked/out.lua')


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

    def pointer(name: str, data: bytes, path_id: int, encoded: bool) -> SimpleNamespace:
        obj = SimpleNamespace(
            type=SimpleNamespace(name='MonoBehaviour'),
            path_id=path_id,
            parse_as_dict=lambda: {'m_Name': name, 'data': data, 'encode': encoded},
        )
        return SimpleNamespace(deref=lambda: obj)

    lua = SimpleNamespace(
        container={
            'src/engine/init.lua': pointer(
                'init',
                bytes.fromhex('8d301105c26b748133747aa67855f72424228fe71d0232b9'),
                11,
                True,
            ),
            'src/ui/init.lua': pointer('init', b'return "ui"', 12, False),
        }
    )
    proto = SimpleNamespace(
        container={
            'proto/Example.proto': pointer(
                'Example',
                bytes.fromhex(
                    '8d074d7e764e9cdc3ca35cabbd866c406bad8a1400da39967b59c5d464d121023'
                    '34dffd3f37217fae92dded2206fd0b839b6f7c5'
                ),
                21,
                True,
            )
        }
    )
    environments = {b'UnityFS\0wrapped lua': lua, b'UnityFS\0wrapped proto': proto}
    monkeypatch.setattr(extract, 'unwrap_bundle', unwrap)
    monkeypatch.setattr(UnityPy, 'load', environments.__getitem__)

    output = tmp_path / 'decoded'
    assert extract_apk(apk, output, 6) == 3
    expected = {
        'sources/example/src/engine/init.lua': b'return {value = 42}',
        'sources/example/src/ui/init.lua': b'return "ui"',
        'sources/gameres_assets_proto_example/proto/Example.proto': (
            b'message Example { optional uint32 value = 1; }'
        ),
    }
    inventory = json.loads((output / 'inventory.json').read_text())
    assert inventory['apk_sha256'] == hashlib.sha256(apk.read_bytes()).hexdigest()
    assert inventory['metadata_sha256'] == hashlib.sha256(metadata).hexdigest()
    assert inventory['seed_offset'] == 6
    assert [bundle['apk_entry'] for bundle in inventory['bundles']] == [
        lua_entry,
        proto_entry,
    ]
    assets = [asset for bundle in inventory['bundles'] for asset in bundle['assets']]
    assert {asset['path'] for asset in assets} == expected.keys()
    for asset in assets:
        data = expected[asset['path']]
        assert (output / asset['path']).read_bytes() == data
        assert asset['size'] == len(data)
        assert asset['sha256'] == hashlib.sha256(data).hexdigest()

    with pytest.raises(FileExistsError):
        extract_apk(apk, output, 6)
    assert (output / 'sources/example/src/ui/init.lua').read_bytes() == b'return "ui"'
