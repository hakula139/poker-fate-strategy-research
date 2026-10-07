import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from google.protobuf.message import DecodeError

from .local_files import private_output
from .packets import Packet
from .schema import Schema
from .session import Session


_PRIVATE_FIELDS = {
    'authorization',
    'key',
    'rdkey',
    'token',
    'verify',
    'password',
    'yidun_risk_check',
    'imei',
    'ip',
    'login_ip',
    'email',
    'nickname',
    'nick',
}
_AUTH_MESSAGES = {'pb.UserLoginREQ', 'pb.UserLoginRSP'}


class Capture:
    def __init__(self, path: Path, schema: Schema, session: Session) -> None:
        self.stream = private_output(path)
        self.schema = schema
        self.session = session
        self.salt = secrets.token_bytes(32)
        self.sequence = 0

    def __enter__(self) -> Capture:
        return self

    def __exit__(self, *_: object) -> None:
        self.stream.close()

    def redact(self, value: Any, field: str = '') -> Any:
        key = field.lower()
        if key in _PRIVATE_FIELDS or any(
            word in key for word in ('password', 'token', 'authorization', 'secret')
        ):
            return '[redacted]'

        if key == 'uid' or key.endswith(('_uid', '_uids')) or key == 'uids':
            if isinstance(value, list):
                return [self.redact(item, 'uid') for item in value]

            if str(value) == str(self.session.uid):
                return 'self'

            digest = hmac.new(self.salt, str(value).encode(), 'sha256').hexdigest()
            return f'player-{digest[:16]}'

        if isinstance(value, dict):
            return {key: self.redact(item, key) for key, item in value.items()}

        if isinstance(value, list):
            return [self.redact(item, field) for item in value]

        if isinstance(value, str):
            return value.replace(self.session.rdkey, '[redacted]')

        return value

    def event(self, event: str, **fields: Any) -> None:
        self._write({'event': event, **fields})

    def packet(
        self,
        packet: Packet,
        direction: Literal['sent', 'received'],
        received_at: str,
        monotonic_ns: int,
    ) -> None:
        self.sequence += 1
        record: dict[str, Any] = {
            'event': 'packet',
            'sequence': self.sequence,
            'direction': direction,
            'received_at': received_at,
            'monotonic_ns': monotonic_ns,
            'recipient': 'self' if direction == 'received' else 'server',
            'name': packet.name,
            'room_id': packet.room_id,
            'payload_size': len(packet.payload),
        }
        if packet.name in _AUTH_MESSAGES:
            record['decode_status'] = 'authentication-omitted'
        else:
            record['payload_sha256'] = hashlib.sha256(packet.payload).hexdigest()
            try:
                record['fields'] = self.schema.decode(packet.name, packet.payload)
                record['decode_status'] = 'decoded'
            except KeyError:
                record['decode_status'] = 'unknown-message'
            except DecodeError:
                record['decode_status'] = 'invalid-protobuf'

        self._write(record)

    def _write(self, record: dict[str, Any]) -> None:
        record.setdefault('recorded_at', datetime.now(UTC).isoformat())
        record.setdefault('monotonic_ns', time.monotonic_ns())
        self.stream.write(json.dumps(self.redact(record), ensure_ascii=False) + '\n')
        self.stream.flush()
