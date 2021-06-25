# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional
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
    group = parser.getgroup("pennsieve")
    # this option will allow to connect directly to pennsieve interface for real testing
    group.addoption(
        "--api-key",
        action="store",
        default=None,
        help="set some specific pennsieve apikey",
    )
    group.addoption(
        "--api-secret",
        action="store",
        default=None,
        help="set some specific pennsieve apisecret",
    )
    group.addoption(
        "--dataset",
        action="store",
        default=None,
        help="set some valid pennsieve dataset ID N:dataset:6b29ddff-86fc-4dc3-bb78-8e572a788a85",
    )
    group.addoption(
        "--file",
        action="store",
        default=None,
        help="set some valid pennsieve file ID N:package:6b29ddff-86fc-4dc3-bb78-8e572a788a85",
    )


@pytest.fixture(scope="session")
def pennsieve_fake_dataset_id() -> Callable:
    def creator() -> str:
        return f"N:dataset:{uuid4()}"

    return creator


@pytest.fixture(scope="session")
def pennsieve_fake_package_id() -> Callable:
    def creator() -> str:
        return f"N:dataset:{uuid4()}"

    return creator


@pytest.fixture(scope="session")
def pennsieve_api_key(request) -> str:
    api_key = request.config.getoption("--api-key")
    if api_key:
        print("Provided pennsieve api key:", api_key)
    return api_key or str(uuid4())


@pytest.fixture(scope="session")
def pennsieve_api_secret(request) -> str:
    api_secret = request.config.getoption("--api-secret")
    if api_secret:
        print("Provided pennsieve api secret:", api_secret)
    return api_secret or str(uuid4())


@pytest.fixture(scope="session")
def pennsieve_dataset_id(request, pennsieve_fake_dataset_id) -> str:
    dataset_id = request.config.getoption("--dataset")

    if dataset_id:
        print("Provided pennsieve dataset id:", dataset_id)
    return dataset_id or pennsieve_fake_dataset_id()


@pytest.fixture(scope="session")
def pennsieve_file_id(request, pennsieve_fake_package_id) -> str:
    package_id = request.config.getoption("--file")

    if package_id:
        print("Provided pennsieve file package id:", package_id)
    return package_id or pennsieve_fake_package_id()


@pytest.fixture(scope="session")
def use_real_pennsieve_interface(request) -> bool:
    return request.config.getoption("--api-key") and request.config.getoption(
        "--api-secret"
    )


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
    use_real_pennsieve_interface: bool,
    mocker,
    pennsieve_api_key: str,
    pennsieve_api_secret: str,
) -> Optional[Any]:
    if use_real_pennsieve_interface:
        yield
    else:
        ps_mock = mocker.patch(
            "simcore_service_datcore_adapter.modules.pennsieve.Pennsieve", autospec=True
        )
        yield ps_mock

        ps_mock.assert_any_call(
            api_secret=pennsieve_api_secret, api_token=pennsieve_api_key
        )


@pytest.fixture()
def pennsieve_dataset_package_mock(mocker, use_real_pennsieve_interface: bool) -> Any:
    if not use_real_pennsieve_interface:
        data_package_mock = mocker.patch(
            "simcore_service_datcore_adapter.modules.pennsieve.pennsieve.models.DataSet",
            autospec=True,
        )
        return data_package_mock


@pytest.fixture()
def pennsieve_data_package_mock(mocker, use_real_pennsieve_interface: bool) -> Any:
    if not use_real_pennsieve_interface:
        data_package_mock = mocker.patch(
            "simcore_service_datcore_adapter.modules.pennsieve.pennsieve.models.DataPackage",
            autospec=True,
        )
        return data_package_mock


@pytest.fixture()
def pennsieve_file_package_mock(mocker, use_real_pennsieve_interface: bool) -> Any:
    if not use_real_pennsieve_interface:
        file_mock = mocker.patch(
            "simcore_service_datcore_adapter.modules.pennsieve.pennsieve.models.File",
            autospec=True,
        )
        return file_mock
