from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .client import Observation, observe
from .errors import InputError
from .local_files import private_json
from .practice import Practice
from .schema import compile_schema
from .session import Session, import_login


def add_protocol_commands(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    schema = commands.add_parser(
        'schema', help='Compile locally extracted protobuf sources.'
    )
    schema.add_argument('sources', type=Path)
    schema.add_argument('--output', type=Path, required=True)
    schema.set_defaults(run=_schema)

    session = commands.add_parser(
        'import-session', help='Import an official login response.'
    )
    session.add_argument('response', type=Path)
    session.add_argument(
        '--version', required=True, help='Version of the authenticating client.'
    )
    session.add_argument(
        '--channel', type=int, required=True, help='Its native distribution channel.'
    )
    session.add_argument('--server-index', type=int, default=0)
    session.add_argument('--output', type=Path, required=True)
    session.set_defaults(run=_session)

    observer = commands.add_parser(
        'observe', help='Connect and record without entering a room.'
    )
    _connection_arguments(observer)
    observer.add_argument(
        '--room-id', type=int, help='Request one existing room snapshot.'
    )
    observer.set_defaults(run=_observe)

    practice = commands.add_parser(
        'practice', help="Enter server Hold'em training and record messages."
    )
    _connection_arguments(practice)
    practice.add_argument(
        '--buy-in',
        type=int,
        required=True,
        help='Training chips, even from 40 to 60 or multiples of 20 from 80 to 400.',
    )
    practice.set_defaults(run=_practice)


def _connection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument(
        '--duration', type=float, default=60, help='Connection duration in seconds.'
    )
    parser.add_argument(
        '--login-timeout',
        type=float,
        default=30,
        help='Login / queue timeout in seconds.',
    )


def _schema(args: argparse.Namespace) -> None:
    descriptors = compile_schema(args.sources)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with args.output.open('xb') as stream:
        stream.write(descriptors)

    print('Compiled local protocol descriptors.')


def _session(args: argparse.Namespace) -> None:
    response = private_json(args.response)
    import_login(response, args.version, args.channel, args.server_index).save(
        args.output
    )
    print('Imported official session. Credentials remain in the private local file.')


def _observe(args: argparse.Namespace) -> None:
    _record(args, Observation(args.duration, args.login_timeout, room_id=args.room_id))


def _practice(args: argparse.Namespace) -> None:
    _record(
        args,
        Observation(args.duration, args.login_timeout, practice=Practice(args.buy_in)),
    )


def _record(args: argparse.Namespace, options: Observation) -> None:
    session = Session.load(args.session)
    try:
        descriptors = args.schema.read_bytes()
    except OSError as error:
        raise InputError(
            'Cannot read the protocol schema. Check its path and permissions.'
        ) from error

    asyncio.run(
        observe(
            session,
            descriptors,
            args.output,
            options,
        )
    )
    print('Recording completed.')
