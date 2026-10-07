import ipaddress
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .local_files import private_input, private_output


def validate_server(url: str) -> None:
    parsed = urlsplit(url)
    local = parsed.hostname in {'127.0.0.1', '::1', 'localhost'}
    if (parsed.scheme != 'wss' and not (local and parsed.scheme == 'ws')) or (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError('Use a credential-free WSS URL, or WS on loopback for tests.')


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
            raise ValueError('Invalid session UID.')

        if not isinstance(self.rdkey, str) or not self.rdkey:
            raise ValueError('Missing session key.')

        if not isinstance(self.version, str) or not self.version:
            raise ValueError('Missing official client version.')

        if type(self.channel) is not int or self.channel < 0:
            raise ValueError('Invalid distribution channel.')

        validate_server(self.server_url)
        ipaddress.ip_address(self.login_ip)
        datetime.fromisoformat(self.captured_at)

    def save(self, path: Path) -> None:
        with private_output(path) as stream:
            json.dump(asdict(self), stream, indent=2)
            stream.write('\n')

    @classmethod
    def load(cls, path: Path) -> Session:
        return cls(**json.loads(private_input(path)))


def import_login(
    response: dict[str, Any], version: str, channel: int, server_index: int = 0
) -> Session:
    if type(response.get('code')) is not int or response['code'] < 0:
        raise ValueError('Official login was not successful.')

    try:
        uid = response['uid']
        if not isinstance(uid, (str, int)) or isinstance(uid, bool):
            raise ValueError('Invalid session UID.')

        if server_index < 0:
            raise ValueError('Server index must be nonnegative.')

        return Session(
            uid=int(uid),
            rdkey=response['rdkey'],
            server_url=response['server']['server'][server_index]['server_host'],
            version=version,
            channel=channel,
            login_ip=response['login_ip'],
            captured_at=datetime.now(UTC).isoformat(),
        )
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            'Official login response is missing session fields.'
        ) from error
