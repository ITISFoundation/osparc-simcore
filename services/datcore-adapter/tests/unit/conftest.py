# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional
from unittest.mock import MagicMock
from uuid import uuid4

import faker
import httpx
import pytest
import respx
import simcore_service_datcore_adapter
from _pytest.monkeypatch import MonkeyPatch
from asgi_lifespan import LifespanManager
from fastapi.applications import FastAPI
from simcore_service_datcore_adapter.modules.pennsieve import _create_pennsieve_client
from starlette import status
from starlette.testclient import TestClient

pytest_plugins = ["pytest_simcore.repository_paths"]


fake = faker.Faker()


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


@pytest.fixture
def app_envs(monkeypatch: MonkeyPatch):
    # disable tracing as together with LifespanManager, it does not remove itself nicely
    monkeypatch.setenv("DATCORE_ADAPTER_TRACING", "null")


@pytest.fixture()
async def initialized_app(app_envs: None, minimal_app: FastAPI) -> Iterator[FastAPI]:
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
        "--collection",
        action="store",
        default=None,
        help="set some valid pennsieve collection ID N:package:6b29ddff-86fc-4dc3-bb78-8e572a788a85",
    )
    group.addoption(
        "--file",
        action="store",
        default=None,
        help="set some valid pennsieve file ID N:package:6b29ddff-86fc-4dc3-bb78-8e572a788a85",
    )


@pytest.fixture(scope="session")
def create_pennsieve_fake_dataset_id() -> Callable[[], str]:
    def creator() -> str:
        return f"N:dataset:{uuid4()}"

    return creator


@pytest.fixture(scope="session")
def create_pennsieve_fake_package_id() -> Callable[[], str]:
    def creator() -> str:
        return f"N:package:{uuid4()}"

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
def pennsieve_dataset_id(request, create_pennsieve_fake_dataset_id) -> str:
    dataset_id = request.config.getoption("--dataset")

    if dataset_id:
        print("Provided pennsieve dataset id:", dataset_id)
    return dataset_id or create_pennsieve_fake_dataset_id()


@pytest.fixture(scope="session")
def pennsieve_collection_id(request, create_pennsieve_fake_package_id) -> str:
    package_id = request.config.getoption("--collection")

    if package_id:
        print("Provided pennsieve collection package id:", package_id)
    return package_id or create_pennsieve_fake_package_id()


@pytest.fixture(scope="session")
def pennsieve_file_id(request, create_pennsieve_fake_package_id) -> str:
    package_id = request.config.getoption("--file")

    if package_id:
        print("Provided pennsieve file package id:", package_id)
    return package_id or create_pennsieve_fake_package_id()


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
        yield None
    else:
        # NOTE: this function is decorated with lru_cache. so before testing we clear it
        _create_pennsieve_client.cache_clear()
        # mock the Pennsieve python client
        ps_mock = mocker.patch(
            "simcore_service_datcore_adapter.modules.pennsieve.Pennsieve", autospec=True
        )
        ps_mock.return_value._api = MagicMock()  # pylint: disable=protected-access
        yield ps_mock

        # TODO: with lru cache it does not work anymore
        ps_mock.assert_any_call(
            api_secret=pennsieve_api_secret, api_token=pennsieve_api_key
        )


@pytest.fixture(scope="module")
def pennsieve_random_fake_datasets(
    create_pennsieve_fake_dataset_id: Callable,
) -> Dict[str, Any]:
    datasets = {
        "datasets": [
            {"content": {"id": create_pennsieve_fake_dataset_id(), "name": fake.text()}}
            for _ in range(10)
        ],
        "totalCount": 20,
    }
    return datasets


@pytest.fixture()
async def pennsieve_subsystem_mock(
    pennsieve_client_mock,
    pennsieve_random_fake_datasets: Dict[str, Any],
    pennsieve_mock_dataset_packages: Dict[str, Any],
    pennsieve_dataset_id: str,
    pennsieve_collection_id: str,
    pennsieve_file_id: str,
):
    if pennsieve_client_mock:
        async with respx.mock as mock:
            # get user
            mock.get("https://api.pennsieve.io/user/").respond(
                status.HTTP_200_OK, json={"id": "some_user_id"}
            )
            # get dataset packages counts
            mock.get(
                f"https://api.pennsieve.io/datasets/{pennsieve_dataset_id}/packageTypeCounts"
            ).respond(
                status.HTTP_200_OK,
                json={"part1": len(pennsieve_mock_dataset_packages["packages"])},
            )
            # get datasets paginated
            mock.get("https://api.pennsieve.io/datasets/paginated").respond(
                status.HTTP_200_OK, json=pennsieve_random_fake_datasets
            )
            # get dataset details
            mock.get(
                f"https://api.pennsieve.io/datasets/{pennsieve_dataset_id}"
            ).respond(
                status.HTTP_200_OK,
                json={
                    "content": {"name": "Some dataset name that is awesome"},
                    "children": pennsieve_mock_dataset_packages["packages"],
                },
            )
            # get datasets packages
            mock.get(
                f"https://api.pennsieve.io/datasets/{pennsieve_dataset_id}/packages"
            ).respond(status.HTTP_200_OK, json=pennsieve_mock_dataset_packages)

            # get collection packages
            mock.get(
                f"https://api.pennsieve.io/packages/{pennsieve_collection_id}"
            ).respond(
                status.HTTP_200_OK,
                json={
                    "content": {"name": "this package name is also awesome"},
                    "children": pennsieve_mock_dataset_packages["packages"],
                    "ancestors": [
                        {"content": {"name": "Bigger guy"}},
                        {"content": {"name": "Big guy"}},
                    ],
                },
            )
            # get packages files
            mock.get(url__regex=r"https://api.pennsieve.io/packages/.+/files$").respond(
                status.HTTP_200_OK,
                json=[{"content": {"size": 12345}}],
            )

            yield mock
    else:
        yield
