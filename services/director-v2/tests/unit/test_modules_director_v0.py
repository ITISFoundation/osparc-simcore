# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import re
import urllib.parse
from pathlib import Path
from random import choice
from typing import Any, NamedTuple
from uuid import uuid4

import pytest
import respx
from fastapi import FastAPI, status
from models_library.services import ServiceDockerData, ServiceKeyVersion
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
    SimcoreServiceLabels,
)
from simcore_service_director_v2.models.schemas.services import ServiceExtras
from simcore_service_director_v2.modules.director_v0 import DirectorV0Client

MOCK_SERVICE_KEY = "simcore/services/dynamic/myservice"
MOCK_SERVICE_VERSION = "1.3.4"


@pytest.fixture
def minimal_director_config(project_env_devel_environment, monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "1")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CATALOG", "null")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "0")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "0")


@pytest.fixture
def mocked_director_v0_service_api(
    minimal_app, entrypoint, exp_data: dict, resp_alias: str
):
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V0.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # lists services
        respx_mock.get(
            urllib.parse.unquote(entrypoint),
            name=resp_alias,
        ).respond(json=exp_data)

        yield respx_mock


@pytest.fixture
def mock_service_key_version() -> ServiceKeyVersion:
    return ServiceKeyVersion(key=MOCK_SERVICE_KEY, version=MOCK_SERVICE_VERSION)


class ForwardToDirectorParams(NamedTuple):
    entrypoint: str
    exp_status: int
    exp_data: dict[str, Any]
    resp_alias: str


def _get_list_services_calls() -> list[ForwardToDirectorParams]:
    return [
        ForwardToDirectorParams(
            entrypoint="services",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": ["service1", "service2"]},
            resp_alias="list_all_services",
        ),
        ForwardToDirectorParams(
            entrypoint="services?service_type=computational",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": ["service1", "service2"]},
            resp_alias="list_computational_services",
        ),
        ForwardToDirectorParams(
            entrypoint="services?service_type=dynamic",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": ["service1", "service2"]},
            resp_alias="list_dynamic_services",
        ),
    ]


def _get_service_version_calls() -> list[ForwardToDirectorParams]:
    # TODO: here we see the return value is currently not validated
    quoted_key = urllib.parse.quote_plus(MOCK_SERVICE_KEY)
    return [
        ForwardToDirectorParams(
            entrypoint=f"/services/{quoted_key}/{MOCK_SERVICE_VERSION}",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": ["stuff about my service"]},
            resp_alias="get_service_version",
        ),
    ]


def _get_service_version_extras_calls() -> list[ForwardToDirectorParams]:
    # TODO: here we see the return value is currently not validated
    quoted_key = urllib.parse.quote_plus(MOCK_SERVICE_KEY)
    return [
        ForwardToDirectorParams(
            entrypoint=f"/services/{quoted_key}/{MOCK_SERVICE_VERSION}/extras",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": "extra stuff about my service"},
            resp_alias="get_service_extras",
        ),
    ]


@pytest.mark.parametrize(
    "entrypoint,exp_status,exp_data,resp_alias",
    _get_list_services_calls()
    + _get_service_version_calls()
    + _get_service_version_extras_calls(),
)
def test_forward_to_director(
    minimal_director_config: None,
    client,
    mocked_director_v0_service_api,
    entrypoint,
    exp_status,
    exp_data: dict,
    resp_alias,
):
    response = client.get(f"v0/{entrypoint}")

    assert response.status_code == exp_status
    assert response.json() == exp_data
    assert mocked_director_v0_service_api[resp_alias].called


@pytest.fixture(scope="session")
def fake_service_details(mocks_dir: Path) -> ServiceDockerData:
    fake_service_path = mocks_dir / "fake_service.json"
    assert fake_service_path.exists()
    fake_service_data = json.loads(fake_service_path.read_text())
    return ServiceDockerData(**fake_service_data)


@pytest.fixture(params=range(len(ServiceExtras.Config.schema_extra["examples"])))
def fake_service_extras(request) -> ServiceExtras:
    extra_example = ServiceExtras.Config.schema_extra["examples"][request.param]
    random_extras = ServiceExtras(**extra_example)
    assert random_extras is not None
    return random_extras


@pytest.fixture
def fake_running_service_details() -> RunningDynamicServiceDetails:
    sample_data = choice(RunningDynamicServiceDetails.Config.schema_extra["examples"])
    return RunningDynamicServiceDetails(**sample_data)


@pytest.fixture
def fake_service_labels() -> dict[str, Any]:
    return choice(SimcoreServiceLabels.Config.schema_extra["examples"])


@pytest.fixture
def mocked_director_service_fcts(
    minimal_app: FastAPI,
    mock_service_key_version: ServiceKeyVersion,
    fake_service_details: ServiceDockerData,
    fake_service_extras: ServiceExtras,
    fake_service_labels: dict[str, Any],
    fake_running_service_details: RunningDynamicServiceDetails,
):
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=minimal_app.state.settings.DIRECTOR_V0.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        quoted_key = urllib.parse.quote_plus(mock_service_key_version.key)
        version = mock_service_key_version.version

        respx_mock.get(
            f"/services/{quoted_key}/{version}", name="get_service_version"
        ).respond(json={"data": [fake_service_details.dict(by_alias=True)]})

        respx_mock.get(
            f"/service_extras/{quoted_key}/{version}", name="get_service_extras"
        ).respond(json={"data": fake_service_extras.dict(by_alias=True)})

        respx_mock.get(
            f"/services/{quoted_key}/{version}/labels", name="get_service_labels"
        ).respond(json={"data": fake_service_labels})

        respx_mock.get(
            re.compile(
                r"running_interactive_services/[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
            ),
            name="get_running_service_details",
        ).respond(
            json={"data": json.loads(fake_running_service_details.json(by_alias=True))}
        )

        yield respx_mock


async def test_get_service_details(
    minimal_director_config: None,
    minimal_app: FastAPI,
    mocked_director_service_fcts,
    mock_service_key_version: ServiceKeyVersion,
    fake_service_details: ServiceDockerData,
):
    director_client: DirectorV0Client = minimal_app.state.director_v0_client
    service_details: ServiceDockerData = await director_client.get_service_details(
        mock_service_key_version
    )

    assert mocked_director_service_fcts["get_service_version"].called
    assert fake_service_details == service_details


async def test_get_service_extras(
    minimal_director_config: None,
    minimal_app: FastAPI,
    mocked_director_service_fcts,
    mock_service_key_version: ServiceKeyVersion,
    fake_service_extras: ServiceExtras,
):
    director_client: DirectorV0Client = minimal_app.state.director_v0_client
    service_extras: ServiceExtras = await director_client.get_service_extras(
        mock_service_key_version.key, mock_service_key_version.version
    )
    assert mocked_director_service_fcts["get_service_extras"].called
    assert fake_service_extras == service_extras


async def test_get_service_labels(
    minimal_director_config: None,
    minimal_app: FastAPI,
    mocked_director_service_fcts,
    fake_service_labels: dict[str, Any],
    mock_service_key_version: ServiceKeyVersion,
):
    director_client: DirectorV0Client = minimal_app.state.director_v0_client

    service_labels: SimcoreServiceLabels = await director_client.get_service_labels(
        mock_service_key_version
    )
    assert mocked_director_service_fcts["get_service_labels"].called
    assert SimcoreServiceLabels(**fake_service_labels) == service_labels


async def test_get_running_service_details(
    minimal_director_config: None,
    minimal_app: FastAPI,
    mocked_director_service_fcts,
    fake_running_service_details: RunningDynamicServiceDetails,
):
    director_client: DirectorV0Client = minimal_app.state.director_v0_client

    service_details: RunningDynamicServiceDetails = (
        await director_client.get_running_service_details(uuid4())
    )
    assert mocked_director_service_fcts["get_running_service_details"].called
    assert fake_running_service_details == service_details
