import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e guided tours options",
        description="oSPARC-e2e guided tours specific parameters",
    )
    group.addoption(
        "--tour-id",
        action="store",
        type=str,
        default=None,
        help="specific tour id to run (e.g., 'projects', 'dashboard', 'navbar'). If not specified, all tours will run.",
    )


@pytest.fixture
def tour_id(request: pytest.FixtureRequest) -> str | None:
    tour = request.config.getoption("--tour-id")
    if tour:
        assert isinstance(tour, str)
    return tour
