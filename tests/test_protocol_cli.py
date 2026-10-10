# cspell:ignore capsys

import json
import sys
from pathlib import Path

import pytest

from poker_fate_strategy_research import cli, protocol_cli
from poker_fate_strategy_research.client import Observation
from poker_fate_strategy_research.session import Session


def failure(
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    monkeypatch.setattr(sys, 'argv', ['poker-fate-strategy', *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    output = capsys.readouterr()
    assert output.out == ''
    return output.err


@pytest.mark.parametrize(
    'command,option,value,message',
    [
        ('practice', '--buy-in', '41', 'Training buy-in'),
        ('observe', '--duration', '0', 'timeouts must be positive'),
    ],
)
def test_invalid_arguments_have_corrective_feedback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    option: str,
    value: str,
    message: str,
) -> None:
    output = failure(
        [
            command,
            '--session',
            'missing',
            '--schema',
            'missing',
            '--output',
            'unused',
            option,
            value,
        ],
        monkeypatch,
        capsys,
    )
    assert message in output


def test_missing_session_has_corrective_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = failure(
        [
            'observe',
            '--session',
            str(tmp_path / 'missing'),
            '--schema',
            'missing',
            '--output',
            'unused',
        ],
        monkeypatch,
        capsys,
    )
    assert 'Private input file was not found' in output


@pytest.mark.parametrize('existing_output', [False, True])
def test_private_file_errors_have_corrective_feedback(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    existing_output: bool,
) -> None:
    source = tmp_path / 'session.json'
    session.save(source)
    output = tmp_path / 'capture.jsonl'
    schema = tmp_path / 'schema.pb'
    schema.write_bytes(b'')
    if existing_output:
        output.write_text('preserved')
    else:
        source.chmod(0o644)

    message = failure(
        [
            'observe',
            '--session',
            str(source),
            '--schema',
            str(schema),
            '--output',
            str(output),
        ],
        monkeypatch,
        capsys,
    )
    if existing_output:
        assert 'Output already exists' in message
        assert output.read_text() == 'preserved'
    else:
        assert 'mode 600 or stricter' in message
        assert not output.exists()

    assert session.rdkey not in message


def test_unexpected_errors_do_not_disclose_credentials(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(path: Path) -> Session:
        raise RuntimeError(session.rdkey)

    monkeypatch.setattr(Session, 'load', fail)
    output = failure(
        [
            'observe',
            '--session',
            str(tmp_path / 'session.json'),
            '--schema',
            'missing',
            '--output',
            'unused',
        ],
        monkeypatch,
        capsys,
    )
    assert 'RuntimeError' in output and session.rdkey not in output


@pytest.mark.parametrize(
    'contents,message',
    [
        ('{"rdkey": "synthetic-secret",', 'valid JSON'),
        ('["synthetic-secret"]', 'JSON object'),
        ('{"rdkey": "synthetic-secret"}', 'missing or unexpected fields'),
    ],
)
def test_invalid_session_files_have_safe_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contents: str,
    message: str,
) -> None:
    source = tmp_path / 'session.json'
    source.write_text(contents)
    source.chmod(0o600)
    output = failure(
        [
            'observe',
            '--session',
            str(source),
            '--schema',
            'missing',
            '--output',
            'unused',
        ],
        monkeypatch,
        capsys,
    )
    assert message in output
    assert 'synthetic-secret' not in output


@pytest.mark.parametrize(
    'arguments,message',
    [
        (['extract', 'missing', '--seed-offset', '0'], 'Check paths and permissions'),
        (['schema', 'missing'], 'No protobuf sources found'),
    ],
)
def test_static_commands_have_corrective_feedback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    message: str,
) -> None:
    output = failure(
        [*arguments, '--output', str(tmp_path / 'output')], monkeypatch, capsys
    )
    assert message in output and 'Traceback' not in output
    assert not (tmp_path / 'output').exists()


def test_connection_failure_is_not_reported_as_a_file_error(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fail(
        session: Session, descriptors: bytes, output: Path, options: Observation
    ) -> None:
        raise ConnectionRefusedError(session.rdkey)

    monkeypatch.setattr(protocol_cli, 'observe', fail)
    source = tmp_path / 'session.json'
    session.save(source)
    schema = tmp_path / 'schema.pb'
    schema.write_bytes(b'')
    output = failure(
        [
            'observe',
            '--session',
            str(source),
            '--schema',
            str(schema),
            '--output',
            str(tmp_path / 'capture.jsonl'),
        ],
        monkeypatch,
        capsys,
    )
    assert 'ConnectionRefusedError' in output
    assert 'paths and permissions' not in output and session.rdkey not in output


@pytest.mark.parametrize(
    'field,value,message',
    [
        ('server_url', 'wss://example.test:synthetic-secret', 'URL is malformed'),
        ('login_ip', 'synthetic-secret', 'valid IP address'),
        ('captured_at', 'synthetic-secret', 'ISO 8601 timestamp'),
    ],
)
def test_invalid_session_values_have_safe_feedback(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: str,
    message: str,
) -> None:
    source = tmp_path / 'session.json'
    session.save(source)
    fields = json.loads(source.read_text())
    fields[field] = value
    source.write_text(json.dumps(fields))
    output = failure(
        [
            'observe',
            '--session',
            str(source),
            '--schema',
            'missing',
            '--output',
            'unused',
        ],
        monkeypatch,
        capsys,
    )
    assert message in output
    assert 'synthetic-secret' not in output
