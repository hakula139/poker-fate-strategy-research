# cspell:ignore fstat o_creat o_wronly

import os
import stat
from pathlib import Path
from typing import TextIO


def private_output(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(descriptor, 'w', encoding='utf-8')


def private_input(path: Path) -> str:
    with path.open(encoding='utf-8') as stream:
        if stat.S_IMODE(os.fstat(stream.fileno()).st_mode) & 0o077:
            raise ValueError('Session input must have mode 600 or stricter.')

        return stream.read()
