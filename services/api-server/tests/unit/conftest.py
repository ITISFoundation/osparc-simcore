# pylint: disable=no-name-in-module
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import sys
from pathlib import Path
from typing import AsyncIterator, Iterator

import httpx
import pytest
import simcore_service_api_server
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx._transports.asgi import ASGITransport
from pytest_simcore.helpers.utils_envs import EnvVarsDict

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytestmark = pytest.mark.asyncio

pytest_plugins = [
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
]


## TEST_ENVIRON ---


@pytest.fixture(scope="session")
def default_test_env_vars() -> dict[str, str]:
    return {
        "WEBSERVER_HOST": "webserver",
        "WEBSERVER_SESSION_SECRET_KEY": Fernet.generate_key().decode("utf-8"),
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "test",
        "POSTGRES_DB": "test",
        "LOG_LEVEL": "debug",
        "SC_BOOT_MODE": "production",
    }


@pytest.fixture(scope="session")
def project_env_devel_vars(project_slug_dir: Path) -> EnvVarsDict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture
def patched_project_env_devel_vars(
    project_env_devel_vars: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in project_env_devel_vars.items():
        monkeypatch.setenv(key, value)

    # overrides
    monkeypatch.setenv("API_SERVER_DEV_FEATURES_ENABLED", "1")


## FOLDER LAYOUT ----


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = CURRENT_DIR.parent.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_api_server"))
    return folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_api_server.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def tests_utils_dir(project_tests_dir: Path) -> Path:
    utils_dir = (project_tests_dir / "utils").resolve()
    assert utils_dir.exists()
    return utils_dir


## APP & TEST CLIENT ------


@pytest.fixture
def app(
    monkeypatch: pytest.MonkeyPatch, default_test_env_vars: dict[str, str]
) -> FastAPI:
    from simcore_service_api_server.core.application import init_app

    # environ
    for key, value in default_test_env_vars.items():
        monkeypatch.setenv(key, value)

    app = init_app()
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            app=app,
            base_url="http://api.testserver.io",
            headers={"Content-Type": "application/json"},
        ) as client:

            assert isinstance(client._transport, ASGITransport)
            # rewires location test's app to client.app
            setattr(client, "app", client._transport.app)

            yield client


@pytest.fixture
def sync_client(app: FastAPI) -> Iterator[TestClient]:
    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(
        app, base_url="http://api.testserver.io", raise_server_exceptions=True
    ) as cli:
        yield cli
