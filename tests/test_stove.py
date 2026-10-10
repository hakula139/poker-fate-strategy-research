import http.client
import json
import stat
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import pytest

from poker_fate_strategy_research import stove
from poker_fate_strategy_research.errors import InputError
from poker_fate_strategy_research.stove import Credentials, SignIn
from poker_fate_strategy_research.stove_http import handler


def configuration() -> dict[str, Any]:
    return {
        'result': 0,
        'value': {
            'categories': {
                'auth': {
                    'client_id': 'synthetic-client',
                    'service_id': 'synthetic-service',
                    'market_game_id': 'synthetic-game',
                    'auth_sign_url': 'https://s-api.onstove.com',
                },
                'base': {'initialize_timeout_sec': 10},
            },
            'gds': {'nation': 'CN'},
            'ip': '192.0.2.1',
        },
    }


def test_credentials_preserve_literal_password_and_existing_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / '.env.local'
    path.write_text('EXISTING_SETTING=keep\n')
    path.chmod(0o600)
    credentials = Credentials('example@example.test', "a'\\b${EXISTING_SETTING}\nc")
    credentials.save(path)
    assert Credentials.load(path) == credentials
    assert 'EXISTING_SETTING=keep' in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert credentials.email not in repr(credentials)
    assert credentials.password not in repr(credentials)


def test_credentials_reject_public_file_and_symlink(tmp_path: Path) -> None:
    path = tmp_path / '.env.local'
    credentials = Credentials('example@example.test', 'synthetic-password')
    credentials.save(path)
    path.chmod(0o644)
    with pytest.raises(InputError, match='600'):
        Credentials.load(path)
    with pytest.raises(InputError, match='600'):
        credentials.save(path)
    link = tmp_path / 'link'
    link.symlink_to(path)
    with pytest.raises(InputError, match='symbolic'):
        credentials.save(link)


def test_captcha_continuation_matches_sdk_and_updates_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / '.env.local'
    Credentials('example@example.test', 'synthetic-password').save(path)
    state = SignIn(path)
    requests: list[tuple[str, str, dict[str, Any], dict[str, str]]] = []
    results: Iterator[dict[str, Any]] = iter(
        [
            {'code': 49700, 'message': 'Verification required'},
            {'code': 49703, 'message': 'Verification invalid'},
            {'code': 0, 'value': {'access_token': 'synthetic-access-token'}},
        ]
    )

    def remote(
        host: str,
        route: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if body is None:
            return configuration()
        assert headers is not None
        requests.append((host, route, body, headers))
        return next(results)

    monkeypatch.setattr(stove, 'request', remote)
    original_nonce = state.csrf
    state.authenticate()
    assert state.phase == 'captcha'
    assert state.csrf != original_nonce
    assert requests[0][2]['gds_info']['ip'] == '192.0.2.1'
    assert 'regist_flag' not in requests[0][2]
    challenge = state.challenge_info()
    constants = challenge['values']['constants']
    assert constants['initialize_timeout_sec'] == 10
    assert constants['gds']['ip'] == '192.0.2.1'
    first_caller = urlsplit(challenge['url']).query
    state.authenticate('synthetic-first-captcha')
    assert state.phase == 'captcha'
    challenge = state.challenge_info()
    assert challenge['values']['constants']['captcha_context']['errorCode'] == 49703
    assert (
        challenge['values']['constants']['captcha_context']['errorMessage']
        == 'Verification invalid'
    )
    assert urlsplit(challenge['url']).query == first_caller
    assert requests[1][2]['regist_flag'] == '0'
    assert requests[1][3]['Captcha-Token'] == 'synthetic-first-captcha'
    assert requests[1][3]['caller-detail'] == state.caller_detail
    state.authenticate('synthetic-second-captcha')
    assert state.phase == 'authenticated'
    assert state.access_token == 'synthetic-access-token'
    output = capsys.readouterr().out
    for secret in (
        'example@example.test',
        'synthetic-password',
        'synthetic-first-captcha',
        'synthetic-access-token',
    ):
        assert secret not in output
        assert secret not in json.dumps(state.public_status())
    state.close()
    assert state.access_token is None
    assert state.credentials is None


@contextmanager
def local_server(state: SignIn) -> Iterator[int]:
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(state))
    state.origin = f'http://127.0.0.1:{server.server_port}'
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        state.close()


def post(
    port: int,
    route: str,
    body: str,
    content_type: str,
    origin: str | None = None,
) -> tuple[int, str]:
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        connection.request(
            'POST',
            route,
            body,
            {
                'Content-Type': content_type,
                'Origin': origin or f'http://127.0.0.1:{port}',
            },
        )
        response = connection.getresponse()
        return response.status, response.read().decode()
    finally:
        connection.close()


def test_http_saves_once_and_continues_after_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SignIn(tmp_path / '.env.local')
    results: Iterator[dict[str, Any]] = iter(
        [
            {'code': 49700},
            {'code': 0, 'value': {'access_token': 'synthetic-access'}},
        ]
    )

    def remote(
        host: str,
        route: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return configuration() if body is None else next(results)

    monkeypatch.setattr(stove, 'request', remote)
    with local_server(state) as port:
        form = urlencode(
            {
                'csrf': state.csrf,
                'email': 'example@example.test',
                'password': 'synthetic-password',
            }
        )
        assert post(port, '/login', form, 'application/x-www-form-urlencoded')[0] == 303
        assert state.phase == 'captcha'
        saved = Credentials.load(state.credentials_path)
        assert saved == Credentials('example@example.test', 'synthetic-password')
        payload = json.dumps({'csrf': state.csrf, 'token': 'synthetic-captcha'})
        code, text = post(port, '/captcha-token', payload, 'application/json')
        assert code == 200
        assert 'synthetic-' not in text
        assert state.phase == 'authenticated'
        assert post(port, '/captcha-token', payload, 'application/json')[0] == 403


@pytest.mark.parametrize('origin', ['null', 'https://example.test'])
def test_http_rejects_foreign_origin_before_saving(
    tmp_path: Path,
    origin: str,
) -> None:
    path = tmp_path / '.env.local'
    state = SignIn(path)
    with local_server(state) as port:
        form = urlencode({'csrf': state.csrf, 'email': 'a', 'password': 'b'})
        assert (
            post(port, '/login', form, 'application/x-www-form-urlencoded', origin)[0]
            == 403
        )
        assert not path.exists()


@pytest.mark.parametrize(
    ('route', 'content_type', 'body'),
    [
        (
            '/login',
            'application/x-www-form-urlencoded',
            urlencode({'csrf': '\u00e9', 'email': 'a', 'password': 'b'}),
        ),
        (
            '/captcha-token',
            'application/json',
            json.dumps({'csrf': '\u00e9', 'token': 'synthetic-captcha'}),
        ),
        (
            '/captcha-token',
            'application/json',
            json.dumps({'csrf': '\ud800', 'token': 'synthetic-captcha'}),
        ),
    ],
)
def test_http_rejects_non_ascii_nonce(
    tmp_path: Path,
    route: str,
    content_type: str,
    body: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / '.env.local'
    state = SignIn(path)
    with local_server(state) as port:
        assert post(port, route, body, content_type)[0] == 403
        assert state.phase == 'credentials'
        assert not path.exists()
    assert capsys.readouterr().err == ''


def test_http_rejects_invalid_unicode_token_before_authentication(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = SignIn(tmp_path / '.env.local')
    state.phase = 'captcha'
    with local_server(state) as port:
        body = json.dumps({'csrf': state.csrf, 'token': '\ud800'})
        assert post(port, '/captcha-token', body, 'application/json')[0] == 400
        assert state.phase == 'captcha'
    assert capsys.readouterr().err == ''
