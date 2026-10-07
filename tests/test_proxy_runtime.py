import http.client
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from poker_fate_strategy_research.session import Session


_PROXY_EXECUTABLE = shutil.which('mitmdump')


class LoginHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = json.dumps(
            {
                'code': 0,
                'uid': 1234,
                'rdkey': 'synthetic-session-key',
                'login_ip': '127.0.0.1',
                'server': {'server': [{'server_host': 'wss://example.test/'}]},
            }
        ).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def proxy(executable: str, output: Path) -> Iterator[int]:
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]

    process = subprocess.Popen(
        [
            executable,
            '-q',
            '--set',
            'flow_detail=0',
            '--listen-host',
            '127.0.0.1',
            '--listen-port',
            str(port),
            '--set',
            f'confdir={output.parent / "proxy-config"}',
            '-s',
            str(root / 'src/poker_fate_strategy_research/login_proxy.py'),
            '--set',
            'login_host=127.0.0.1',
            '--set',
            'client_channel=3',
            '--set',
            f'session_output={output}',
        ],
        env={**os.environ, 'PYTHONPATH': str(root / 'src')},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_proxy(process, port)
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)


def _wait_for_proxy(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        assert process.poll() is None, 'Bundled proxy failed to start.'
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.1)

    pytest.fail('Bundled proxy did not start within 15 seconds.')


@pytest.mark.skipif(
    _PROXY_EXECUTABLE is None,
    reason='Run inside nix develop to test the bundled proxy runtime.',
)
def test_bundled_proxy_captures_local_login(tmp_path: Path) -> None:
    assert _PROXY_EXECUTABLE is not None

    output = tmp_path / 'session.json'
    server = ThreadingHTTPServer(('127.0.0.1', 0), LoginHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with proxy(_PROXY_EXECUTABLE, output) as port:
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            connection.request(
                'POST',
                f'http://127.0.0.1:{server.server_port}/login',
                '{}',
                {'Version': '1.7.0'},
            )
            response = connection.getresponse()
            assert response.status == 200
            response.read()
            connection.close()
            session = Session.load(output)
            assert session.uid == 1234 and session.rdkey == 'synthetic-session-key'
            assert session.version == '1.7.0' and session.channel == 3
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)
