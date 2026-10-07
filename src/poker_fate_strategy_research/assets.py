import hashlib
from pathlib import Path, PurePosixPath
from typing import TypedDict, cast

import UnityPy
from UnityPy.classes.Object import Object
from UnityPy.classes.PPtr import PPtr

from .bundles import decode_asset


class AssetRecord(TypedDict):
    name: str
    container_path: str
    path_id: int
    encoded: int
    path: str
    size: int
    sha256: str


def asset_path(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.name:
        raise ValueError(f'Unsafe asset name: {name!r}')

    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Asset path escapes output directory: {name!r}')

    return target


def extract_assets(
    data: bytes, bundle_root: Path, output: Path, *, proto: bool
) -> list[AssetRecord]:
    environment = UnityPy.load(data)
    assets: list[AssetRecord] = []
    for container_name, pointer in sorted(environment.container.items()):
        obj = cast(PPtr[Object], pointer).deref()
        if obj.type.name != 'MonoBehaviour':
            continue

        asset = obj.parse_as_dict()
        decoded = bytes(asset['data'])
        if asset['encode']:
            decoded = decode_asset(decoded, proto=proto)

        target = asset_path(bundle_root, container_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(decoded)

        assets.append(
            {
                'name': asset['m_Name'],
                'container_path': container_name,
                'path_id': obj.path_id,
                'encoded': asset['encode'],
                'path': target.relative_to(output).as_posix(),
                'size': len(decoded),
                'sha256': hashlib.sha256(decoded).hexdigest(),
            }
        )

    return assets
