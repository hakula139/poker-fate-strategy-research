from __future__ import annotations

import http.client
import json
import platform
import secrets
import threading
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import getproxies

from dotenv import dotenv_values, set_key

from .errors import InputError
from .local_files import private_input, private_output


CONFIG_PATH = (
    '/ssg/access/clients/sdk/0.1.1/com.pokerfate.play'
    '?policy_grp=mobilesdk&client_lang=en&device_nation=CN&game_version=0.1.1'
)
CAPTCHA_URL = 'https://accounts.onstove.com/auth/captcha'


@dataclass(frozen=True)
class Credentials:
    email: str = field(repr=False)
    password: str = field(repr=False)

    @classmethod
    def load(cls, path: Path) -> Credentials | None:
        if not path.exists():
            return None
        values = dotenv_values(stream=StringIO(private_input(path)), interpolate=False)
        email, password = values.get('STOVE_EMAIL'), values.get('STOVE_PASSWORD')
        if not email and not password:
            return None
        if not email or not password:
            raise InputError(
                'Set both STOVE_EMAIL and STOVE_PASSWORD in the local file.'
            )
        return cls(email, password)

    def save(self, path: Path) -> None:
        if path.is_symlink():
            raise InputError('The credential file must not be a symbolic link.')
        if path.exists():
            private_input(path)
        else:
            with private_output(path):
                pass
        for key, value in (
            ('STOVE_EMAIL', self.email),
            ('STOVE_PASSWORD', self.password),
        ):
            set_key(path, key, value, quote_mode='always')


def request(
    host: str,
    path: str,
    body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    if host not in {'api.onstove.com', 's-api.onstove.com'}:
        raise InputError('Unrecognized STOVE destination.')
    headers = {
        'SDK-Version': '2.8.3',
        'Game-Version': '1.7.0',
        'Accept-Language': 'en',
        'platform-type': 'MOBILE',
    }
    if extra_headers:
        headers.update(extra_headers)
    data = None if body is None else json.dumps(body).encode()
    if data is not None:
        headers['Content-Type'] = 'application/json'
    proxy_url = getproxies().get('https')
    if proxy_url:
        proxy = urlsplit(proxy_url)
        if (
            proxy.scheme != 'http'
            or not proxy.hostname
            or proxy.username
            or proxy.password
        ):
            raise InputError('Unsupported HTTPS proxy configuration.')
        connection = http.client.HTTPSConnection(
            proxy.hostname, proxy.port or 80, timeout=20
        )
        connection.set_tunnel(host, 443)
    else:
        connection = http.client.HTTPSConnection(host, timeout=20)
    try:
        connection.request('GET' if data is None else 'POST', path, data, headers)
        response = connection.getresponse()
        if response.status != 200:
            raise InputError(f'STOVE returned HTTP {response.status}.')
        payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise InputError('STOVE response exceeds the size limit.')
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise InputError('Unrecognized STOVE response.')
        return result
    finally:
        connection.close()


class SignIn:
    def __init__(self, credentials_path: Path):
        self.credentials_path = credentials_path
        self.credentials = Credentials.load(credentials_path)
        self.lock = threading.Lock()
        self.csrf = secrets.token_urlsafe(32)
        self.phase = 'credentials'
        self.status = (
            'Sign in with your saved credentials.'
            if self.credentials
            else 'Enter your STOVE email and password once.'
        )
        self.access_token: str | None = None
        self.captcha_code = 49700
        self.captcha_message = ''
        self.caller_uuid = str(uuid.uuid4())
        self.device_id = secrets.token_hex(16)
        self.origin = ''
        self.last_code: int | None = None
        self.observed_at: str | None = None
        self._config: dict[str, Any] | None = None

    @property
    def caller_detail(self) -> str:
        checksum = f'{zlib.crc32(self.caller_uuid.encode()):08x}'
        value = self.caller_uuid
        for offset in range(0, len(checksum), 2):
            value = value.replace('-', checksum[offset : offset + 2], 1)
        return value

    def public_status(self) -> dict[str, object]:
        return {
            'phase': self.phase,
            'status': self.status,
            'code': self.last_code,
            'observed_at': self.observed_at,
            'saved_credentials': self.credentials is not None,
        }

    def configuration(self) -> dict[str, Any]:
        if self._config is not None:
            return self._config
        config = request('api.onstove.com', CONFIG_PATH)
        if config.get('result') != 0:
            raise InputError('STOVE configuration rejected.')
        value = dict(config['value'])
        value['gds'] = {**value['gds'], 'ip': value['ip']}
        self._config = value
        return value

    def challenge_info(self) -> dict[str, Any]:
        value = self.configuration()
        auth = value['categories']['auth']
        if auth.get('web_captcha_url', CAPTCHA_URL) != CAPTCHA_URL:
            raise InputError('Unrecognized challenge destination.')
        constants = {
            key: item
            for category in value['categories'].values()
            for key, item in category.items()
        }
        constants.update(value['gds'])
        constants.update(
            {
                'gds': value['gds'],
                'ip': value['ip'],
                'environment': 'live',
                'captcha_context': {
                    'join_method': 'SM',
                    'captcha_reason': self.captcha_code,
                    'userinfo_reason': 'signin',
                    'is_link': 'N',
                    'stove_join': 'false',
                    'errorCode': self.captcha_code,
                    'errorMessage': self.captcha_message,
                },
            }
        )
        return {
            'url': CAPTCHA_URL
            + '?'
            + urlencode(
                {
                    'callerDetail': self.caller_detail,
                    'callerId': 'STOVESDK-AuthUI-2.8.3',
                    # cspell:disable-next-line
                    'siteKey': 't7RuKauo6Dbl0cmHdzEZkXFbpjEkxQus',
                }
            ),
            'values': {
                'constants': constants,
                'access_token': '',
                'game_language': 'en',
            },
            'device': {
                'market_game_id': auth.get('market_game_id', ''),
                'device_info': self.device_info(),
            },
            'csrf': self.csrf,
        }

    def device_info(self) -> dict[str, str]:
        return {
            'language': 'en',
            'device_id': self.device_id,
            'device_name': 'local-research-client',
            'country': 'CN',
            'os_name': platform.system().lower(),
            'os_version': platform.mac_ver()[0] or platform.release(),
        }

    def authenticate(self, captcha_token: str | None = None) -> None:
        if self.credentials is None:
            raise InputError('No saved STOVE credentials.')
        self.phase = 'signing-in'
        self.status = 'Signing in to STOVE...'
        try:
            self._authenticate(captcha_token)
        except Exception as error:
            self.phase = 'stopped'
            self.status = f'Sign-in stopped ({type(error).__name__}).'
            print(self.status, flush=True)
        finally:
            self.csrf = secrets.token_urlsafe(32)

    def _authenticate(self, captcha_token: str | None) -> None:
        started = monotonic()
        value = self.configuration()
        auth = value['categories']['auth']
        if auth['auth_sign_url'] != 'https://s-api.onstove.com':
            raise InputError('Unrecognized authentication destination.')
        assert self.credentials is not None
        body = {
            'client_id': auth['client_id'],
            'service_id': auth['service_id'],
            'provider_cd': 'SM',
            'device_info': self.device_info(),
            'gds_info': value['gds'],
            'provider_data': {
                'user_id': self.credentials.email,
                'password': self.credentials.password,
            },
        }
        headers = {
            'caller-ID': 'STOVESDK-AuthUI-2.8.3-' + str(auth['service_id']),
            'caller-detail': self.caller_detail,
            'Transaction-ID': str(uuid.uuid4()),
        }
        if captcha_token is not None:
            headers['Captcha-Token'] = captcha_token
            body['regist_flag'] = '0'
            length = len(captcha_token.encode())
            handoff = monotonic() - started
            print(
                f'CAPTCHA received: {length} bytes. Handoff: {handoff:.1f} seconds.',
                flush=True,
            )
        response = request(
            's-api.onstove.com', '/sign/v2.0/mobile/signin', body, headers
        )
        code = response.get('code', response.get('return_code'))
        if type(code) is not int:
            raise InputError('Unrecognized STOVE result code.')
        self.last_code = code
        self.observed_at = datetime.now(UTC).isoformat()
        if code == 0:
            token = response.get('value', {}).get('access_token')
            if not isinstance(token, str) or not token:
                raise InputError('Accepted response has no user token.')
            self.access_token = token
            self.phase = 'authenticated'
            self.status = 'STOVE sign-in succeeded. No game connection has been made.'
        elif code in (49700, 49703):
            self.captcha_code = code
            message = response.get('message', response.get('return_message', ''))
            self.captcha_message = message if isinstance(message, str) else ''
            self.phase = 'captcha'
            self.status = f'STOVE requires CAPTCHA verification ({code}).'
        elif code == 43000:
            self.phase = 'stopped'
            self.status = (
                'This email is not registered with STOVE. '
                "A game-linked email uses Poker Fate's email sign-in."
            )
        else:
            self.phase = 'stopped'
            self.status = (
                f'STOVE sign-in returned {code}. No game connection has been made.'
            )
        print(
            f'STOVE authentication result: {code}. Observed at: {self.observed_at}.',
            flush=True,
        )

    def close(self) -> None:
        self.access_token = None
        self.credentials = None
        self.captcha_message = ''
        self._config = None
