import pytest
from pydantic import ByteSize


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="oSPARC-e2e specific parameters"
    )
    group.addoption(
        "--file-size",
        action="store",
        type=str,
        default="20Gib",
        help="large file size in human readable form",
    )


@pytest.fixture(scope="session")
def large_file_size(request: pytest.FixtureRequest) -> ByteSize:
    file_size = request.config.getoption("--file-size")
    assert file_size is not None
    assert isinstance(file_size, str)
    return ByteSize(file_size)
