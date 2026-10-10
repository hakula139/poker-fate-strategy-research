import argparse
import sys
from pathlib import Path

from .client import ClientError
from .errors import InputError
from .extract import extract_apk
from .protocol_cli import add_protocol_commands


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
    extract.set_defaults(run=_extract)
    add_protocol_commands(commands)

    args = parser.parse_args()
    if args.command in {'extract', 'schema'}:
        args.run(args)
        return

    try:
        args.run(args)
    except KeyboardInterrupt:
        print('Interrupted.', file=sys.stderr)
        raise SystemExit(130) from None
    except (ClientError, InputError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as error:
        print(
            f'Unexpected failure ({type(error).__name__}).',
            file=sys.stderr,
        )
        raise SystemExit(1) from None


def _extract(args: argparse.Namespace) -> None:
    count = extract_apk(args.apk, args.output, args.seed_offset)
    print(f'Decoded {count} assets. Inventory: {args.output / "inventory.json"}')
