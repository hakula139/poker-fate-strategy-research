from __future__ import annotations

import argparse
import platform
import plistlib
import shutil
import subprocess
from http.server import ThreadingHTTPServer
from pathlib import Path

from .errors import InputError
from .stove import SignIn
from .stove_http import handler


def add_stove_command(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    command = commands.add_parser(
        'stove-login', help='Sign in to STOVE with a local WebKit verification window.'
    )
    command.add_argument('--credentials', type=Path, default=Path('.env.local'))
    command.add_argument('--output', type=Path, default=Path('work/stove-auth'))
    command.add_argument('--port', type=int, default=0)
    command.add_argument('--no-open', action='store_true')
    command.set_defaults(run=_run)


def build_window(output: Path, origin: str) -> Path:
    if platform.system() != 'Darwin':
        raise InputError(
            'The verification window requires macOS and Apple Swift tools.'
        )
    compiler = shutil.which('xcrun')
    if compiler is None:
        raise InputError('Apple Swift tools are unavailable.')
    bundle = output.resolve() / 'STOVE Verification.app'
    contents = bundle / 'Contents'
    binary = contents / 'MacOS' / 'STOVE Verification'
    resources = contents / 'Resources'
    binary.parent.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent / 'stove_webkit'
    subprocess.run(
        [
            compiler,
            'swiftc',
            '-parse-as-library',
            '-module-cache-path',
            str(output.resolve() / 'swift-cache'),
            str(source / 'CaptchaWindow.swift'),
            '-o',
            str(binary),
        ],
        check=True,
    )
    shutil.copyfile(source / 'challenge_bridge.js', resources / 'challenge_bridge.js')
    with (contents / 'Info.plist').open('wb') as stream:
        plistlib.dump(
            {
                'CFBundleExecutable': 'STOVE Verification',
                'CFBundleName': 'STOVE Verification',
                'CFBundleIdentifier': 'xyz.hakula.poker-fate-research.verification',
                'CFBundlePackageType': 'APPL',  # cspell:disable-line
                'CFBundleVersion': '1',
                'NSHighResolutionCapable': True,
                'NSPrincipalClass': 'NSApplication',
                'ResearchOrigin': origin,
            },
            stream,
        )
    return bundle


def _run(args: argparse.Namespace) -> None:
    state = SignIn(args.credentials)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(state))
    state.origin = f'http://127.0.0.1:{server.server_port}'
    try:
        bundle = build_window(args.output, state.origin)
        print(f'Local STOVE sign-in: {state.origin}', flush=True)
        print(f'Verification window: {bundle}', flush=True)
        if not args.no_open:
            subprocess.run(['open', '-n', str(bundle)], check=True)
        server.serve_forever()
    finally:
        server.server_close()
        state.close()
