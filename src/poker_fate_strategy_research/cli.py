import argparse
from pathlib import Path

from .extract import extract_apk


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Tools for reproducible Poker Fate research.'
    )
    commands = parser.add_subparsers(dest='command', required=True)
    extract = commands.add_parser('extract', help='Decode APK sources and index them.')
    extract.add_argument('apk', type=Path)
    extract.add_argument('--output', type=Path, required=True)
    extract.add_argument(
        '--seed-offset',
        type=lambda value: int(value, 0),
        required=True,
        help='Seed field offset in global-metadata.dat for this APK build.',
    )
    args = parser.parse_args()
    count = extract_apk(args.apk, args.output, args.seed_offset)
    print(f'Decoded {count} assets. Inventory: {args.output / "inventory.json"}')
