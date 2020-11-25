# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import json
import re
import urllib.parse
from collections import namedtuple
from pathlib import Path
from random import randint
from typing import Callable, List
from uuid import uuid4

import pytest
import respx
from fastapi import FastAPI, status
from models_library.services import ServiceDockerData, ServiceKeyVersion
from simcore_service_director_v2.models.schemas.services import (
    RunningServiceDetails,
    ServiceExtras,
)
from simcore_service_director_v2.modules.director_v0 import DirectorV0Client


@pytest.fixture(autouse=True)
def minimal_director_config(project_env_devel_environment, monkeypatch):
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


ForwardToDirectorParams = namedtuple(
    "ForwardToDirectorParams", "entrypoint,exp_status,exp_data,resp_alias"
)


def _get_list_services_calls() -> List[ForwardToDirectorParams]:
    return [
        ForwardToDirectorParams(
            entrypoint="/v0/services",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": ["service1", "service2"]},
            resp_alias="list_all_services",
        ),
        ForwardToDirectorParams(
            entrypoint="/v0/services?service_type=computational",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": ["service1", "service2"]},
            resp_alias="list_computational_services",
        ),
        ForwardToDirectorParams(
            entrypoint="/v0/services?service_type=dynamic",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": ["service1", "service2"]},
            resp_alias="list_dynamic_services",
        ),
    ]


def _get_service_version_calls() -> List[ForwardToDirectorParams]:
    # TODO: here we see the return value is currently not validated
    return [
        ForwardToDirectorParams(
            entrypoint="/v0/services/simcore%2Fservices%2Fdynamic%2Fmyservice/1.3.4",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": ["stuff about my service"]},
            resp_alias="get_service_version",
        )
    ]


def _get_service_version_extras_calls() -> List[ForwardToDirectorParams]:
    # TODO: here we see the return value is currently not validated
    return [
        ForwardToDirectorParams(
            entrypoint="/v0/services/simcore%2Fservices%2Fdynamic%2Fmyservice/1.3.4/extras",
            exp_status=status.HTTP_200_OK,
            exp_data={"data": "extra stuff about my service"},
            resp_alias="get_service_extras",
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
def fake_running_service_details(
    random_json_from_schema: Callable,
) -> RunningServiceDetails:
    random_data = random_json_from_schema(RunningServiceDetails.schema_json(indent=2))
    # fix port stuff, the randomiser does not understand positive ints
    KEYS_TO_FIX = ["published_port", "service_port"]
    for k in KEYS_TO_FIX:
        if k in random_data:
            random_data[k] = randint(1, 50000)
    random_details = RunningServiceDetails(**random_data)

    return random_details


@pytest.fixture
def mocked_director_service_fcts(
    minimal_app: FastAPI,
    fake_service_details: ServiceDockerData,
    fake_service_extras: ServiceExtras,
    fake_running_service_details: RunningServiceDetails,
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
        pattern = re.compile(
            r"v0/running_interactive_services/[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
        )
        respx_mock.get(
            pattern,
            content={"data": fake_running_service_details.dict(by_alias=True)},
            alias="get_running_service_details",
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
    assert fake_service_extras == service_extras


async def test_get_running_service_details(
    minimal_app: FastAPI,
    mocked_director_service_fcts,
    fake_running_service_details: RunningServiceDetails,
):

    director_client: DirectorV0Client = minimal_app.state.director_v0_client

    service_details: RunningServiceDetails = (
        await director_client.get_running_service_details(str(uuid4()))
    )
    assert mocked_director_service_fcts["get_running_service_details"].called
    assert fake_running_service_details == service_details
