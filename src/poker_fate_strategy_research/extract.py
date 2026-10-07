import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import cast
from zipfile import ZipFile

import UnityPy
from UnityPy.classes.Object import Object
from UnityPy.classes.PPtr import PPtr

from .bundles import decode_asset, seed_from_metadata, unwrap_bundle


def asset_path(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.name:
        raise ValueError(f'Unsafe asset name: {name!r}')
    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Asset path escapes output directory: {name!r}')
    return target


def extract_apk(apk: Path, output: Path, seed_offset: int) -> int:
    output.mkdir(parents=True, exist_ok=False)
    with apk.open('rb') as stream:
        apk_hash = hashlib.file_digest(stream, 'sha256').hexdigest()

    bundles = []
    asset_count = 0
    with ZipFile(apk) as archive:
        metadata = archive.read('assets/bin/Data/Managed/Metadata/global-metadata.dat')
        seed = seed_from_metadata(metadata, seed_offset)
        for entry in archive.namelist():
            if not entry.endswith('.bundle') or not (
                entry.startswith('assets/aa/Android/gameres_assets_src/')
                or entry.startswith('assets/aa/Android/gameres_assets_src_')
                or entry.startswith('assets/aa/Android/gameres_assets_proto_')
            ):
                continue

            wrapped = archive.read(entry)
            unwrapped = unwrap_bundle(wrapped, seed)
            environment = UnityPy.load(unwrapped)
            proto = '/gameres_assets_proto_' in entry
            bundle_root = output / 'sources' / PurePosixPath(entry).stem
            assets = []
            for container_name, pointer in sorted(environment.container.items()):
                obj = cast(PPtr[Object], pointer).deref()
                if obj.type.name != 'MonoBehaviour':
                    continue
                asset = obj.parse_as_dict()
                data = bytes(asset['data'])
                if asset['encode']:
                    data = decode_asset(data, proto=proto)
                name = asset['m_Name']
                target = asset_path(bundle_root, container_name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(data)
                assets.append(
                    {
                        'name': name,
                        'container_path': container_name,
                        'path_id': obj.path_id,
                        'encoded': asset['encode'],
                        'path': target.relative_to(output).as_posix(),
                        'size': len(data),
                        'sha256': hashlib.sha256(data).hexdigest(),
                    }
                )

            if not assets:
                raise ValueError(f'No Lua / protocol assets decoded from {entry}')
            bundles.append(
                {
                    'apk_entry': entry,
                    'wrapped_sha256': hashlib.sha256(wrapped).hexdigest(),
                    'unwrapped_sha256': hashlib.sha256(unwrapped).hexdigest(),
                    'assets': assets,
                }
            )
            asset_count += len(assets)

    if not bundles:
        raise ValueError('No source / protocol bundles found in the APK')
    inventory = {
        'apk_sha256': apk_hash,
        'metadata_sha256': hashlib.sha256(metadata).hexdigest(),
        'seed_offset': seed_offset,
        'bundles': bundles,
    }
    (output / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    return asset_count
