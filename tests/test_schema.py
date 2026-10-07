import pytest
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet
from google.protobuf.message import DecodeError

from poker_fate_strategy_research.schema import Schema


def test_decode_preserves_field_presence_and_dependencies() -> None:
    base = FileDescriptorProto(name='base.proto', package='pb', syntax='proto2')
    child = base.message_type.add(name='Cards')
    child.field.add(name='cards', number=1, type=5, label=3)
    dependent = FileDescriptorProto(name='room.proto', package='pb', syntax='proto2')
    dependent.dependency.append('base.proto')
    room = dependent.message_type.add(name='Room')
    room.field.add(name='cards', number=1, type=11, type_name='.pb.Cards', label=1)
    room.field.add(name='stage', number=2, type=5, label=1)
    schema = Schema(FileDescriptorSet(file=[dependent, base]).SerializeToString())
    payload = schema.encode('pb.Room', {'cards': {'cards': [1, 52]}})
    assert schema.decode('pb.Room', payload) == {'cards': {'cards': [1, 52]}}
    assert schema.decode('pb.Room', schema.encode('pb.Room', {'stage': 0})) == {
        'stage': 0
    }

    with pytest.raises(KeyError):
        schema.decode('pb.Unknown', b'')

    with pytest.raises(DecodeError):
        schema.decode('pb.Room', b'\x0a\x05')


def test_missing_dependency() -> None:
    file = FileDescriptorProto(name='room.proto', dependency=['missing.proto'])
    with pytest.raises(ValueError, match='dependencies'):
        Schema(FileDescriptorSet(file=[file]).SerializeToString())
