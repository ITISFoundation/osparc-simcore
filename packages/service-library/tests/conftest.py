# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import servicelib
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.file_extra",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_service_library_fixtures",
    "pytest_simcore.tmp_path_extra",
    "pytest_simcore.schemas",
]


@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(servicelib.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("packages/service-library")), (
        "%s not look like rootdir" % root_dir
    )
    return root_dir


@pytest.fixture
def fake_data_dict(faker: Faker) -> dict[str, Any]:
    data = {
        "uuid_as_UUID": faker.uuid4(cast_to=None),
        "uuid_as_str": faker.uuid4(),
        "int": faker.pyint(),
        "float": faker.pyfloat(),
        "str": faker.pystr(),
    }
    data["object"] = deepcopy(data)
    return data


def pytest_addoption(parser: pytest.Parser):
    group = parser.getgroup(
        "external_environment",
        description="Replaces mocked services with real ones by passing actual environs and connecting directly to external services",
    )
    group.addoption(
        "--external-envfile",
        action="store",
        type=Path,
        default=None,
        help="Path to an env file. Consider passing a link to repo configs, i.e. `ln -s /path/to/osparc-ops-config/repo.config`",
    )


@pytest.fixture(scope="session")
def external_environment(request: pytest.FixtureRequest) -> EnvVarsDict:
    """
    If a file under test folder prefixed with `.env-secret` is present,
    then this fixture captures it.

    This technique allows reusing the same tests to check against
    external development/production servers
    """
    envs = {}
    if envfile := request.config.getoption("--external-envfile"):
        print("🚨 EXTERNAL `envfile` option detected. Loading", envfile, "...")

        assert isinstance(envfile, Path)
        assert envfile.is_file()

        envs = load_dotenv(envfile)

    return envs
