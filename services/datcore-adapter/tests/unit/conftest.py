# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path
from typing import Iterator

import httpx
import pytest
import simcore_service_datcore_adapter
from asgi_lifespan import LifespanManager
from fastapi.applications import FastAPI
from starlette.testclient import TestClient

pytest_plugins = ["pytest_simcore.repository_paths"]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "datcore-adapter"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_datcore_adapter"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_datcore_adapter.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture()
def minimal_app() -> FastAPI:
    from simcore_service_datcore_adapter.main import the_app

    return the_app


@pytest.fixture()
def client(minimal_app: FastAPI) -> TestClient:
    with TestClient(minimal_app) as cli:
        return cli


@pytest.fixture()
async def initialized_app(minimal_app: FastAPI) -> Iterator[FastAPI]:
    async with LifespanManager(minimal_app):
        yield minimal_app


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> httpx.AsyncClient:

    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://datcore-adapter.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client
