# pylint: disable=redefined-outer-name
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="oSPARC-e2e specific parameters"
    )
    group.addoption(
        "--service-opening-waiting-timeout",
        action="store",
        type=int,
        default=300000,  # 5 mins
        help="Defines a waiting timeout in milliseconds for opening a service.",
    )


@pytest.fixture
def service_opening_waiting_timeout(request: pytest.FixtureRequest) -> int:
    service_opening_waiting_timeout = request.config.getoption(
        "--service-opening-waiting-timeout"
    )
    assert isinstance(service_opening_waiting_timeout, int)
    return service_opening_waiting_timeout
