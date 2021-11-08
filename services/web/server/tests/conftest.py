# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import json
import logging
import sys
from pathlib import Path
from typing import Dict

import pytest
import simcore_service_webserver
from pytest_simcore.helpers.utils_login import LoggedUser, UserDict
from simcore_service_webserver.db_models import UserRole

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


log = logging.getLogger(__name__)

# mute noisy loggers
logging.getLogger("openapi_spec_validator").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


# imports the fixtures for the integration tests
pytest_plugins = [
    "pytest_simcore.celery_service",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.services_api_mocks_for_aiohttp_clients",
    "pytest_simcore.simcore_services",
    "pytest_simcore.tmp_path_extra",
    "pytest_simcore.websocket_client",
]


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """osparc-simcore installed directory"""
    dirpath = Path(simcore_service_webserver.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir) -> Path:
    service_dir = osparc_simcore_root_dir / "services" / "web" / "server"
    assert service_dir.exists()
    assert any(service_dir.glob("src/simcore_service_webserver"))
    return service_dir


@pytest.fixture(scope="session")
def api_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "webserver"
    assert specs_dir.exists()
    return specs_dir


@pytest.fixture(scope="session")
def tests_data_dir(project_tests_dir: Path) -> Path:
    data_dir = project_tests_dir / "data"
    assert data_dir.exists()
    return data_dir


@pytest.fixture(scope="session")
def fake_data_dir(tests_data_dir: Path) -> Path:
    # legacy
    return tests_data_dir


@pytest.fixture
def fake_project(tests_data_dir: Path) -> Dict:
    fpath = tests_data_dir / "fake-project.json"
    assert fpath.exists()
    return json.loads(fpath.read_text())


@pytest.fixture()
async def logged_user(client, user_role: UserRole) -> UserDict:
    """adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        print("-----> logged in user", user["name"], user_role)
        yield user
        print("<----- logged out user", user["name"], user_role)
