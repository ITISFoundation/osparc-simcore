# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=no-name-in-module

import pytest
from pydantic import TypeAdapter


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="oSPARC-e2e specific parameters"
    )
    group.addoption(
        "--check-videostreaming",
        action="store_true",
        default=False,
        help="check if video streaming is functional",
    )


@pytest.fixture(scope="session")
def check_videostreaming(request: pytest.FixtureRequest) -> bool:
    check_video = request.config.getoption("--check-videostreaming")
    return TypeAdapter(bool).validate_python(check_video)
