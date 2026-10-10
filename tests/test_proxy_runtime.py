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
                'code': int(self.headers['X-Test-Code']),
                'uid': 1234,
                'rdkey': self.headers['X-Test-Key'],
                'authorization': 'unused-secret',
                'login_ip': '127.0.0.1',
                'server': {'server': [{'server_host': 'wss://example.test/'}]},
            }
        ).encode()
        self.send_response(int(self.headers['X-Test-Status']))
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST

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


def request(
    proxy_port: int,
    server_port: int,
    *,
    host: str = '127.0.0.1',
    method: str = 'POST',
    path: str = '/login',
    code: int = 0,
    status: int = 200,
    key: str = 'synthetic-session-key',
) -> None:
    connection = http.client.HTTPConnection('127.0.0.1', proxy_port, timeout=10)
    try:
        connection.request(
            method,
            f'http://{host}:{server_port}{path}',
            '{}',
            {
                'Version': '1.7.0',
                'X-Test-Code': str(code),
                'X-Test-Status': str(status),
                'X-Test-Key': key,
            },
        )
        response = connection.getresponse()
        assert response.status == status
        response.read()
    finally:
        connection.close()


@pytest.mark.skipif(
    _PROXY_EXECUTABLE is None,
    reason='Run inside nix develop to test the bundled proxy runtime.',
)
@pytest.mark.parametrize('accepted_code', [0, -6])
def test_bundled_proxy_captures_selected_login_once(
    tmp_path: Path, accepted_code: int
) -> None:
    assert _PROXY_EXECUTABLE is not None

    output = tmp_path / 'session.json'
    server = ThreadingHTTPServer(('127.0.0.1', 0), LoginHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with proxy(_PROXY_EXECUTABLE, output) as port:
            request(port, server.server_port, host='localhost')
            assert not output.exists()
            request(port, server.server_port, method='GET')
            assert not output.exists()
            request(port, server.server_port, path='/unrelated')
            assert not output.exists()
            request(port, server.server_port, status=403)
            assert not output.exists()
            request(port, server.server_port, code=-5)
            assert not output.exists()

            request(port, server.server_port, code=accepted_code)
            session = Session.load(output)
            assert session.uid == 1234 and session.rdkey == 'synthetic-session-key'
            assert session.version == '1.7.0' and session.channel == 3
            assert 'authorization' not in json.loads(output.read_text())

            request(port, server.server_port, key='replacement-key')
            assert Session.load(output) == session
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)
