# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=no-name-in-module

import pytest
from pydantic import TypeAdapter


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("oSparc e2e options", description="oSPARC-e2e specific parameters")
    group.addoption(
        "--check-videostreaming",
        action="store_true",
        default=False,
        help="check if video streaming is functional",
    )
    group.addoption(
        "--use-plus-button",
        action="store_true",
        default=False,
        help="The service key option will be used as the plus button ID instead of service key",
    )


@pytest.fixture(scope="session")
def check_videostreaming(request: pytest.FixtureRequest) -> bool:
    check_video = request.config.getoption("--check-videostreaming")
    return TypeAdapter(bool).validate_python(check_video)


@pytest.fixture(scope="session")
def use_plus_button(request: pytest.FixtureRequest) -> bool:
    use_plus_button = request.config.getoption("--use-plus-button")
    return TypeAdapter(bool).validate_python(use_plus_button)
