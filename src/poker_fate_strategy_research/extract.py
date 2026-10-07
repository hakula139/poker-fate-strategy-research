import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import TypedDict
from zipfile import ZipFile

from .assets import AssetRecord, extract_assets
from .bundles import seed_from_metadata, unwrap_bundle


class BundleRecord(TypedDict):
    apk_entry: str
    wrapped_sha256: str
    unwrapped_sha256: str
    assets: list[AssetRecord]


def _extract_bundle(data: bytes, entry: str, seed: int, output: Path) -> BundleRecord:
    unwrapped = unwrap_bundle(data, seed)
    bundle_root = output / 'sources' / PurePosixPath(entry).stem
    assets = extract_assets(
        unwrapped, bundle_root, output, proto='/gameres_assets_proto_' in entry
    )
    if not assets:
        raise ValueError(f'No Lua / protocol assets decoded from {entry}')

    return {
        'apk_entry': entry,
        'wrapped_sha256': hashlib.sha256(data).hexdigest(),
        'unwrapped_sha256': hashlib.sha256(unwrapped).hexdigest(),
        'assets': assets,
    }


def extract_apk(apk: Path, output: Path, seed_offset: int) -> int:
    output.mkdir(parents=True, exist_ok=False)
    with apk.open('rb') as stream:
        apk_hash = hashlib.file_digest(stream, 'sha256').hexdigest()

    bundles = []
    with ZipFile(apk) as archive:
        metadata = archive.read('assets/bin/Data/Managed/Metadata/global-metadata.dat')
        seed = seed_from_metadata(metadata, seed_offset)
        for entry in archive.namelist():
            if not entry.endswith('.bundle') or not entry.startswith(
                (
                    'assets/aa/Android/gameres_assets_src/',
                    'assets/aa/Android/gameres_assets_src_',
                    'assets/aa/Android/gameres_assets_proto_',
                )
            ):
                continue

            bundles.append(_extract_bundle(archive.read(entry), entry, seed, output))

    if not bundles:
        raise ValueError('No source / protocol bundles found in the APK')

    inventory = {
        'apk_sha256': apk_hash,
        'metadata_sha256': hashlib.sha256(metadata).hexdigest(),
        'seed_offset': seed_offset,
        'bundles': bundles,
    }
    (output / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    return sum(len(bundle['assets']) for bundle in bundles)
