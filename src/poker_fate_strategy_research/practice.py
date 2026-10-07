from dataclasses import dataclass
from typing import Any

from .session import Session


@dataclass(frozen=True)
class Practice:
    buy_in: int

    def __post_init__(self) -> None:
        if not 40 <= self.buy_in <= 400 or self.buy_in % 2:
            raise ValueError('Training buy-in must be an even integer from 40 to 400.')

    def fields(self, session: Session) -> dict[str, Any]:
        return {
            'boot': 2,
            'game_type': 40010101,
            'lobby_coin': 10100001,
            'byin_chips': self.buy_in,
            'wait_blind': True,
            'ip': session.login_ip,
        }
