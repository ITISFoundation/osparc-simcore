import pytest
from pydantic import ByteSize, parse_obj_as


def parametrized_file_size(size_str: str):
    return pytest.param(parse_obj_as(ByteSize, size_str), id=size_str)
