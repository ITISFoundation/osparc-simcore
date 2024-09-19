import pytest
from _pytest.mark.structures import ParameterSet
from pydantic import ByteSize, TypeAdapter


def byte_size_ids(val) -> str | None:
    if isinstance(val, ByteSize):
        return val.human_readable()
    return None


def parametrized_file_size(size_str: str) -> ParameterSet:
    return pytest.param(TypeAdapter(ByteSize).validate_python(size_str), id=size_str)
