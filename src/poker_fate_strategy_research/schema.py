import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import DecodeError
from google.protobuf.message_factory import GetMessageClass

from .errors import InputError


@dataclass(frozen=True)
class DecodedMessage:
    fields: dict[str, Any]
    unknown_fields: bool


class Schema:
    def __init__(self, descriptors: bytes) -> None:
        files = FileDescriptorSet.FromString(descriptors)
        self.pool = DescriptorPool()
        pending = {file.name: file for file in files.file}
        loaded: set[str] = set()
        while pending:
            ready = [
                file
                for file in pending.values()
                if all(dependency in loaded for dependency in file.dependency)
            ]
            if not ready:
                raise ValueError('Descriptor dependencies are missing or cyclic.')

            for file in ready:
                self.pool.Add(file)
                loaded.add(file.name)
                del pending[file.name]

    def encode(self, name: str, fields: dict[str, Any]) -> bytes:
        descriptor = self.pool.FindMessageTypeByName(name)
        message = GetMessageClass(descriptor)()
        ParseDict(fields, message)
        return message.SerializeToString()

    def decode(self, name: str, payload: bytes) -> dict[str, Any]:
        return self.inspect(name, payload).fields

    def inspect(self, name: str, payload: bytes) -> DecodedMessage:
        descriptor = self.pool.FindMessageTypeByName(name)
        message = GetMessageClass(descriptor).FromString(payload)
        if not message.IsInitialized():
            raise DecodeError('Protocol message is missing required fields.')

        original = message.SerializeToString()
        fields = MessageToDict(
            message, preserving_proto_field_name=True, use_integers_for_enums=True
        )
        message.DiscardUnknownFields()
        return DecodedMessage(fields, original != message.SerializeToString())


def compile_schema(directory: Path) -> bytes:
    directory = directory.resolve()
    files = sorted(path.name for path in directory.glob('*.proto'))
    if not files:
        raise InputError('No protobuf sources found. Check the source directory.')

    result = subprocess.run(
        [
            'protoc',
            f'--proto_path={directory}',
            '--include_imports',
            '--descriptor_set_out=/dev/stdout',
            *files,
        ],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise InputError('Protocol compilation failed:\n' + result.stderr.decode())

    Schema(result.stdout)
    return result.stdout
