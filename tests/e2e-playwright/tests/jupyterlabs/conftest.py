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
def large_file_size(request: pytest.FixtureRequest) -> ByteSize:
    file_size = request.config.getoption("--large-file-size")
    if not file_size:
        return ByteSize(0)
    assert file_size is not None
    assert isinstance(file_size, str)
    return TypeAdapter(ByteSize).validate_python(file_size)
