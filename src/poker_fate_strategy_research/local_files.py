import json
import os
import stat
from pathlib import Path
from typing import Any, TextIO

from .errors import InputError


def private_output(path: Path) -> TextIO:
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise InputError('Output already exists. Choose a new output path.') from error
    except PermissionError as error:
        raise InputError(
            'Cannot create the output. Check directory permissions.'
        ) from error

    return os.fdopen(descriptor, 'w', encoding='utf-8')


def private_input(path: Path) -> str:
    try:
        with path.open(encoding='utf-8') as stream:
            if stat.S_IMODE(os.fstat(stream.fileno()).st_mode) & 0o077:
                raise InputError('Private input must have mode 600 or stricter.')

            return stream.read()
    except FileNotFoundError as error:
        raise InputError('Private input file was not found. Check its path.') from error
    except PermissionError as error:
        raise InputError(
            'Cannot read the private input. Check file permissions.'
        ) from error
    except UnicodeError as error:
        raise InputError('Private input must be UTF-8 text.') from error


def private_json(path: Path) -> Any:
    try:
        return json.loads(private_input(path))
    except json.JSONDecodeError as error:
        raise InputError('Private input must contain valid JSON.') from error
