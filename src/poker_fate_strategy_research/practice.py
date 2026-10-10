from dataclasses import dataclass
from typing import Any

from .errors import InputError
from .session import Session


@dataclass(frozen=True)
class Practice:
    buy_in: int

    def __post_init__(self) -> None:
        if self.buy_in not in (*range(40, 62, 2), *range(80, 401, 20)):
            raise InputError(
                'Training buy-in must be even from 40 to 60 or a multiple of 20 '
                'from 80 to 400.'
            )

    def fields(self, session: Session) -> dict[str, Any]:
        return {
            'boot': 2,
            'game_type': 40010101,
            'lobby_coin': 10100001,
            'byin_chips': self.buy_in,
            'wait_blind': True,
            'ip': session.login_ip,
        }
