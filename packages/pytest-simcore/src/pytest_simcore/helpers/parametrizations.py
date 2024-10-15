import pytest
from _pytest.mark.structures import ParameterSet
from common_library.pydantic_type_adapters import ByteSizeAdapter
from pydantic import ByteSize


def byte_size_ids(val) -> str | None:
    if isinstance(val, ByteSize):
        return val.human_readable()
    return None


def parametrized_file_size(size_str: str) -> ParameterSet:
    return pytest.param(ByteSizeAdapter.validate_python(size_str), id=size_str)
