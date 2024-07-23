import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="oSPARC-e2e specific parameters"
    )
    group.addoption(
        "--num-sleepers",
        action="store",
        type=int,
        default=2,
        help="number of sleepers to create",
    )

    group.addoption(
        "--input-sleep-time",
        action="store",
        type=int,
        default=None,
        help="number of seconds each sleeper sleeps",
    )


@pytest.fixture
def num_sleepers(request: pytest.FixtureRequest) -> int:
    num = request.config.getoption("--num-sleepers")
    assert isinstance(num, int)
    return num


@pytest.fixture
def input_sleep_time(request: pytest.FixtureRequest) -> int | None:
    return request.config.getoption("--input-sleep-time", default=None)
