# Collection of tests fixtures for integration testing
# NOTE: keep this module import-light (no third-party imports at module level): it is
# auto-imported as a pytest11 plugin in EVERY environment installing pytest-simcore,
# including minimal test suites that never use its docker/xdist fixtures. Import
# optional dependencies lazily inside the fixtures that need them.
import os
from importlib.metadata import version

import pytest

# NOTE: this ensures that assertion printouts are nicely formatted and complete see https://lorepirri.com/pytest-register-assert-rewrite.html
pytest.register_assert_rewrite("pytest_simcore.helpers")

__version__: str = version("pytest-simcore")


def pytest_addoption(parser: pytest.Parser):
    simcore_group = parser.getgroup("simcore", description="pytest-simcore options")
    simcore_group.addoption(
        "--keep-docker-up",
        action="store_true",
        default=False,
        help="Keep stack/registry up after fixtures closes",
    )


@pytest.fixture(scope="session")
def keep_docker_up(request: pytest.FixtureRequest) -> bool:
    flag: bool = bool(request.config.getoption(name="--keep-docker-up", default=False))
    return flag


@pytest.fixture(autouse=True)
def _xdist_reseed_faker(request: pytest.FixtureRequest) -> None:
    """`faker`'s own pytest plugin seeds every session with the SAME fixed seed (for
    reproducibility), so concurrent xdist workers (separate processes) generate the exact
    same "random" sequence and collide whenever tests rely on `faker` for uniqueness (e.g. a
    docker resource name built from `faker.uuid4()`). Re-seeds `faker` per worker so
    concurrent workers diverge, while staying deterministic/reproducible within a worker.
    No-op when not running under xdist (`faker` isn't even instantiated in that case, so this
    adds no overhead to the common, non-xdist test run).
    """
    if "PYTEST_XDIST_WORKER" not in os.environ:
        return

    from faker import Faker  # noqa: PLC0415

    from .helpers.xdist import get_worker_id  # noqa: PLC0415

    worker_id = get_worker_id(request)
    faker: Faker = request.getfixturevalue("faker")
    digits = "".join(ch for ch in worker_id if ch.isdigit())
    worker_ordinal = int(digits) if digits else 0
    faker.seed_instance(worker_ordinal + 1)


@pytest.fixture(scope="session")
def is_pdb_enabled(request: pytest.FixtureRequest):
    """Returns true if tests are set to use interactive debugger, i.e. --pdb"""
    options = request.config.option
    return options.usepdb
