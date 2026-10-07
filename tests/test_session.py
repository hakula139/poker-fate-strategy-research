import json
import stat
from pathlib import Path

import pytest

from poker_fate_strategy_research.session import Session, import_login


def login_response() -> dict[str, object]:
    return {
        'code': 0,
        'uid': '1234',
        'rdkey': 'synthetic-session-key',
        'authorization': 'unused-secret',
        'login_ip': '127.0.0.1',
        'server': {'server': [{'server_host': 'wss://example.test/socket'}]},
    }


def test_session_import_and_private_storage(tmp_path: Path) -> None:
    session = import_login(login_response(), '1.7.0', 3)
    path = tmp_path / 'session.json'
    session.save(path)
    assert Session.load(path) == session
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert 'authorization' not in json.loads(path.read_text())
    assert 'synthetic-session-key' not in repr(session)
    assert '1234' not in repr(session)

    with pytest.raises(FileExistsError):
        session.save(path)

    path.chmod(0o644)
    with pytest.raises(ValueError, match='600'):
        Session.load(path)


@pytest.mark.parametrize(
    'field,value',
    [
        ('code', -5),
        ('code', False),
        ('uid', True),
        ('uid', 0),
        ('uid', 2**63),
        ('uid', 'invalid'),
        ('rdkey', ''),
        ('login_ip', 'invalid'),
        ('server', {'server': [{'server_host': 'wss://example.test/?token=secret'}]}),
        ('server', {'server': [{'server_host': 'ws://example.test/'}]}),
        ('server', {'server': []}),
    ],
)
def test_reject_invalid_login(field: str, value: object) -> None:
    response = login_response()
    response[field] = value
    with pytest.raises(ValueError):
        import_login(response, '1.7.0', 3)
