# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=no-name-in-module

import pytest
from pydantic import ByteSize, TypeAdapter


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="oSPARC-e2e specific parameters"
    )
    group.addoption(
        "--large-file-size",
        action="store",
        type=str,
        default=None,
        help="large file size in human readable form",
    )


@pytest.fixture(scope="session")
def large_file_block_size() -> ByteSize:
    return TypeAdapter(ByteSize).validate_python("64Mib")


@pytest.fixture(scope="session")
def large_file_size(
    request: pytest.FixtureRequest, large_file_block_size: ByteSize
) -> ByteSize:
    file_size = request.config.getoption("--large-file-size")
    if not file_size:
        return ByteSize(0)
    assert file_size is not None
    assert isinstance(file_size, str)
    validated_file_size = TypeAdapter(ByteSize).validate_python(file_size)
    assert (
        validated_file_size >= large_file_block_size
    ), f"{validated_file_size.human_readable()} must be larger than {large_file_block_size.human_readable()}!"
    return validated_file_size
