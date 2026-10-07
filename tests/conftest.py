import pytest
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet

from poker_fate_strategy_research.session import Session


@pytest.fixture
def descriptors() -> bytes:
    file = FileDescriptorProto(name='test.proto', package='pb', syntax='proto2')
    messages = {
        'UserLoginREQ': [('uid', 3), ('key', 9), ('ver', 9), ('chnl', 5)],
        'UserLoginRSP': [('code', 5)],
        'HeartBeatREQ': [],
        'HeartBeatRSP': [('server_timestamp', 5)],
        'GetRoomDataREQ': [('roomid', 5)],
        'QuickStartREQ': [
            ('boot', 3),
            ('game_type', 5),
            ('lobby_coin', 5),
            ('byin_chips', 3),
            ('wait_blind', 8),
            ('ip', 9),
        ],
        'QuickStartRSP': [('code', 5)],
        'EnterRoomRSP': [('code', 5), ('roomid', 5), ('game_type', 5)],
        'GetRoomDataRSP': [('code', 5), ('roomid', 5), ('game_type', 5)],
        'CardsBRC': [('uid', 3), ('stage', 5), ('card', 5), ('key', 9)],
    }
    for name, fields in messages.items():
        message = file.message_type.add(name=name)
        for index, (field_name, kind) in enumerate(fields, start=1):
            message.field.add(name=field_name, number=index, type=kind, label=1)

    return FileDescriptorSet(file=[file]).SerializeToString()


@pytest.fixture
def session() -> Session:
    return Session(
        1234,
        'synthetic-session-key',
        'wss://example.test/',
        '1.7.0',
        3,
        '127.0.0.1',
        '2026-10-07T00:00:00+00:00',
    )
