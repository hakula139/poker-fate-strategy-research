import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


def test_login_proxy_only_saves_selected_successful_login(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[str] = []
    options = SimpleNamespace(
        session_output=str(tmp_path / 'session.json'),
        client_channel=3,
        login_host='example.test',
    )
    context = SimpleNamespace(
        options=options,
        log=SimpleNamespace(
            error=messages.append,
            info=messages.append,
        ),
    )
    stub = ModuleType('mitmproxy')
    stub.ctx = context  # type: ignore[attr-defined]
    stub.http = SimpleNamespace(HTTPFlow=object)  # type: ignore[attr-defined]
    loader = ModuleType('mitmproxy.addonmanager')
    loader.Loader = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, 'mitmproxy', stub)
    monkeypatch.setitem(sys.modules, 'mitmproxy.addonmanager', loader)
    monkeypatch.delitem(
        sys.modules, 'poker_fate_strategy_research.login_proxy', raising=False
    )
    module = importlib.import_module('poker_fate_strategy_research.login_proxy')
    addon = module.LoginCapture()
    response: dict[str, Any] = {
        'code': -5,
        'uid': 1234,
        'rdkey': 'synthetic-session-key',
        'authorization': 'unused-secret',
        'login_ip': '127.0.0.1',
        'server': {'server': [{'server_host': 'wss://example.test/socket'}]},
    }
    request = SimpleNamespace(
        host='unrelated.test',
        method='POST',
        path='/login',
        headers={'Version': '1.7.0'},
    )
    flow = SimpleNamespace(
        request=request,
        response=SimpleNamespace(
            status_code=200,
            json=lambda: response,
        ),
    )
    addon.response(flow)
    assert not Path(options.session_output).exists()
    request.host = 'example.test'
    addon.response(flow)
    assert not Path(options.session_output).exists()
    response['code'] = 0
    addon.response(flow)
    stored = json.loads(Path(options.session_output).read_text())
    assert stored['rdkey'] == 'synthetic-session-key' and stored['channel'] == 3
    assert stored['version'] == '1.7.0' and 'authorization' not in stored
    response['rdkey'] = 'replacement-key'
    addon.response(flow)
    assert (
        json.loads(Path(options.session_output).read_text())['rdkey'] == stored['rdkey']
    )
    assert 'synthetic-session-key' not in ' '.join(messages)
    assert 'unused-secret' not in ' '.join(messages)
