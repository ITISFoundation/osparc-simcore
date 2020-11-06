import json
import urllib.parse
from pathlib import Path
from typing import Callable, List, Tuple

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
import pytest
import respx
from fastapi import FastAPI, status
from models_library.services import ServiceDockerData, ServiceKeyVersion
from simcore_service_director_v2.models.schemas.services import ServiceExtras
from simcore_service_director_v2.modules.director_v0 import DirectorV0Client


@pytest.fixture(autouse=True)
def minimal_director_config(monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "1")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")


@pytest.fixture
def mocked_director_v0_service_api(minimal_app, entrypoint, exp_data, resp_alias):
    with respx.mock(
        base_url=minimal_app.state.settings.director_v0.base_url(include_tag=False),
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # lists services
        respx_mock.get(
            urllib.parse.unquote(entrypoint),
            content=exp_data,
            alias=resp_alias,
        )

        yield respx_mock


def _get_list_services_calls() -> List[Tuple]:
    return [
        (
            "/v0/services",
            status.HTTP_200_OK,
            {"data": ["service1", "service2"]},
            "list_all_services",
        ),
        (
            "/v0/services?service_type=computational",
            status.HTTP_200_OK,
            {"data": ["service1", "service2"]},
            "list_computational_services",
        ),
        (
            "/v0/services?service_type=dynamic",
            status.HTTP_200_OK,
            {"data": ["service1", "service2"]},
            "list_dynamic_services",
        ),
    ]


def _get_service_version_calls() -> List[Tuple]:
    # TODO: here we see the return value is currently not validated
    return [
        (
            "/v0/services/simcore%2Fservices%2Fdynamic%2Fmyservice/1.3.4",
            status.HTTP_200_OK,
            {"data": ["stuff about my service"]},
            "get_service_version",
        )
    ]


def _get_service_version_extras_calls() -> List[Tuple]:
    # TODO: here we see the return value is currently not validated
    return [
        (
            "/v0/services/simcore%2Fservices%2Fdynamic%2Fmyservice/1.3.4/extras",
            status.HTTP_200_OK,
            {"data": "extra stuff about my service"},
            "get_service_extras",
        )
    ]


@pytest.mark.parametrize(
    "entrypoint,exp_status,exp_data,resp_alias",
    _get_list_services_calls()
    + _get_service_version_calls()
    + _get_service_version_extras_calls(),
)
def test_forward_to_director(
    client, mocked_director_v0_service_api, entrypoint, exp_status, exp_data, resp_alias
):
    response = client.get(entrypoint)

    assert response.status_code == exp_status
    assert response.json() == exp_data
    assert mocked_director_v0_service_api[resp_alias].called


@pytest.fixture(scope="session")
def fake_service_details(mocks_dir: Path) -> ServiceDockerData:
    fake_service_path = mocks_dir / "fake_service.json"
    assert fake_service_path.exists()
    fake_service_data = json.loads(fake_service_path.read_text())
    return ServiceDockerData(**fake_service_data)


@pytest.fixture
def fake_service_extras(random_json_from_schema: Callable) -> ServiceExtras:
    random_extras = ServiceExtras(
        **random_json_from_schema(ServiceExtras.schema_json(indent=2))
    )
    return random_extras


@pytest.fixture
def mocked_director_service_fcts(
    minimal_app: FastAPI, fake_service_details, fake_service_extras
):
    with respx.mock(
        base_url=minimal_app.state.settings.director_v0.base_url(include_tag=False),
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get(
            "/v0/services/simcore%2Fservices%2Fdynamic%2Fmyservice/1.3.4",
            content={"data": [fake_service_details.dict(by_alias=True)]},
            alias="get_service_version",
        )

        respx_mock.get(
            "/v0/service_extras/simcore%2Fservices%2Fdynamic%2Fmyservice/1.3.4",
            content={"data": fake_service_extras.dict(by_alias=True)},
            alias="get_service_extras",
        )

        yield respx_mock


async def test_get_service_details(
    minimal_app: FastAPI,
    mocked_director_service_fcts,
    fake_service_details: ServiceDockerData,
):
    director_client: DirectorV0Client = minimal_app.state.director_v0_client
    service = ServiceKeyVersion(
        key="simcore/services/dynamic/myservice", version="1.3.4"
    )
    service_details: ServiceDockerData = await director_client.get_service_details(
        service
    )
    assert mocked_director_service_fcts["get_service_version"].called
    assert fake_service_details == service_details


async def test_get_service_extras(
    minimal_app: FastAPI,
    mocked_director_service_fcts,
    fake_service_extras: ServiceExtras,
):
    director_client: DirectorV0Client = minimal_app.state.director_v0_client
    service = ServiceKeyVersion(
        key="simcore/services/dynamic/myservice", version="1.3.4"
    )
    service_extras: ServiceExtras = await director_client.get_service_extras(service)
    assert mocked_director_service_fcts["get_service_extras"].called
    assert fake_service_extras == fake_service_extras
