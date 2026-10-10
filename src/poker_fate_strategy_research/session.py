import ipaddress
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit

from .errors import InputError
from .local_files import private_json, private_output


def validate_server(url: str) -> None:
    if not isinstance(url, str):
        raise InputError('Session server URL must be a string.')

    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError as error:
        raise InputError('Session server URL is malformed.') from error

    local = parsed.hostname in {'127.0.0.1', '::1', 'localhost'}
    if (parsed.scheme != 'wss' and not (local and parsed.scheme == 'ws')) or (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise InputError('Use a credential-free WSS URL, or WS on loopback for tests.')


@dataclass(frozen=True)
class Session:
    uid: int = field(repr=False)
    rdkey: str = field(repr=False)
    server_url: str
    version: str
    channel: int
    login_ip: str = field(repr=False)
    captured_at: str

    def __post_init__(self) -> None:
        if type(self.uid) is not int or not 0 < self.uid < 2**63:
            raise InputError('Invalid session UID.')

        if not isinstance(self.rdkey, str) or not self.rdkey:
            raise InputError('Missing session key.')

        if not isinstance(self.version, str) or not self.version:
            raise InputError('Missing official client version.')

        if type(self.channel) is not int or not 0 <= self.channel < 2**31:
            raise InputError('Invalid distribution channel.')

        validate_server(self.server_url)
        if not isinstance(self.login_ip, str):
            raise InputError('Session login IP must be a valid IP address.')

        try:
            ipaddress.ip_address(self.login_ip)
        except ValueError as error:
            raise InputError('Session login IP must be a valid IP address.') from error

        try:
            datetime.fromisoformat(self.captured_at)
        except (TypeError, ValueError) as error:
            raise InputError(
                'Session capture time must be an ISO 8601 timestamp.'
            ) from error

    def save(self, path: Path) -> None:
        with private_output(path) as stream:
            json.dump(asdict(self), stream, indent=2)
            stream.write('\n')

    @classmethod
    def load(cls, path: Path) -> Self:
        fields = private_json(path)
        if not isinstance(fields, dict):
            raise InputError('Session file must contain a JSON object.')

        try:
            return cls(**fields)
        except TypeError as error:
            raise InputError(
                'Session file has missing or unexpected fields.'
            ) from error


def import_login(
    response: object, version: str, channel: int, server_index: int = 0
) -> Session:
    if not isinstance(response, dict):
        raise InputError('Official login response must be a JSON object.')

    code = response.get('code')
    if type(code) is not int or (code < 0 and code != -6):
        raise InputError('Official login was not successful.')

    try:
        uid = response['uid']
        if not isinstance(uid, (str, int)) or isinstance(uid, bool):
            raise InputError('Invalid session UID.')

        if server_index < 0:
            raise InputError('Server index must be nonnegative.')

        try:
            uid = int(uid)
        except ValueError as error:
            raise InputError('Invalid session UID.') from error

        return Session(
            uid=uid,
            rdkey=response['rdkey'],
            server_url=response['server']['server'][server_index]['server_host'],
            version=version,
            channel=channel,
            login_ip=response['login_ip'],
            captured_at=datetime.now(UTC).isoformat(),
        )
    except (KeyError, IndexError, TypeError) as error:
        raise InputError(
            'Official login response is missing session fields.'
        ) from error
