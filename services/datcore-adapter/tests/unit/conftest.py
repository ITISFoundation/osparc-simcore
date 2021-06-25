# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator
from uuid import uuid4

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


@pytest.fixture(scope="session")
def mocks_dir(project_slug_dir: Path) -> Path:
    mocks = project_slug_dir / "tests" / "mocks"
    assert mocks.exists()
    return mocks


@pytest.fixture(scope="session")
def pennsieve_mock_dataset_packages(mocks_dir: Path) -> Dict[str, Any]:
    ps_packages_file = mocks_dir / "ps_packages.json"
    assert ps_packages_file.exists()
    return json.loads(ps_packages_file.read_text())


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


# --------------------- PENNSIEVE RELATED Fixtures


def pytest_addoption(parser):
    group = parser.getgroup("simcore")
    # this option will allow to connect directly to pennsieve interface for real testing
    group.addoption(
        "--with-pennsieve",
        action="store",
        default={},
        help="--with-pennsieve: {api_key=MYKEY, api_secret=MYSECRET}",
    )


@pytest.fixture(scope="session")
def with_pennsieve(request) -> Dict[str, str]:
    ps_apis = request.config.getoption("--with-pennsieve")

    if ps_apis:
        ps_apis_config = json.loads(ps_apis)
        assert "api_key" in ps_apis_config
        assert "api_secret" in ps_apis_config
        print("Using pennsieve with following api token:", ps_apis_config)
        return ps_apis_config

    print("mocking pennsieve interface")
    return dict()


@pytest.fixture(scope="session")
def pennsieve_api_key(with_pennsieve: Dict[str, str]) -> str:
    return with_pennsieve.get("api_key", str(uuid4()))


@pytest.fixture(scope="session")
def pennsieve_api_secret(with_pennsieve: Dict[str, str]) -> str:
    return with_pennsieve.get("api_secret", str(uuid4()))


@pytest.fixture(scope="session")
def pennsieve_api_headers(
    pennsieve_api_key: str, pennsieve_api_secret: str
) -> Dict[str, str]:
    return {
        "x-datcore-api-key": pennsieve_api_key,
        "x-datcore-api-secret": pennsieve_api_secret,
    }


@pytest.fixture()
def pennsieve_client_mock(
    mocker, pennsieve_api_key: str, pennsieve_api_secret: str
) -> Any:
    ps_mock = mocker.patch(
        "simcore_service_datcore_adapter.modules.pennsieve.Pennsieve", autospec=True
    )
    yield ps_mock

    ps_mock.assert_any_call(
        api_secret=pennsieve_api_secret, api_token=pennsieve_api_key
    )


@pytest.fixture(scope="session")
def pennsieve_fake_dataset_id() -> Callable:
    def creator() -> str:
        return f"N:dataset:{uuid4()}"

    return creator
