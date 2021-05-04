# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, Iterator, Union

import pytest
import simcore_service_comp_resource_manager
import yaml
from asgi_lifespan import LifespanManager
from dotenv import dotenv_values
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytestmark = pytest.mark.asyncio

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.pydantic_models",
]


## TEST_ENVIRON ---


@pytest.fixture(scope="session")
def environment() -> Dict:
    env = {
        "LOG_LEVEL": "debug",
        "SC_BOOT_MODE": "production",
    }
    return env


@pytest.fixture(scope="session")
def project_env_devel_dict(project_slug_dir: Path) -> Dict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture
def project_env_devel_environment(project_env_devel_dict, monkeypatch):
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)

    # overrides
    monkeypatch.setenv("comp_resource_manager_DEV_FEATURES_ENABLED", "1")


## FOLDER LAYOUT ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = current_dir.parent.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_comp_resource_manager"))
    return folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_comp_resource_manager.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def tests_utils_dir(project_tests_dir: Path) -> Path:
    utils_dir = (project_tests_dir / "utils").resolve()
    assert utils_dir.exists()
    return utils_dir


## APP & TEST CLIENT -----------------------------------------------------------------------


@pytest.fixture
def app(monkeypatch, environment) -> FastAPI:
    # patching environs
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    from simcore_service_comp_resource_manager.core.application import init_app

    app = init_app()
    return app


@pytest.fixture
async def initialized_app(app: FastAPI) -> Iterator[FastAPI]:
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def client(initialized_app: FastAPI) -> Iterator[AsyncClient]:
    async with AsyncClient(
        app=initialized_app,
        base_url="http://crm.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def sync_client(app: FastAPI) -> TestClient:
    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(
        app, base_url="http://api.testserver.io", raise_server_exceptions=True
    ) as cli:
        yield cli
