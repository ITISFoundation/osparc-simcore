# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import urllib
from collections import namedtuple
from typing import Any, Dict, Optional

import pytest
import respx
from fastapi import FastAPI
from httpx import URL, QueryParams
from models_library.service_settings import SimcoreService
from simcore_service_director_v2.models.domains.dynamic_services import (
    DynamicServiceCreate,
)
from starlette import status
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def minimal_director_config(project_env_devel_environment, monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "1")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_SCHEDULER_ENABLED", "0")


@pytest.fixture(scope="session")
def dynamic_sidecar_headers() -> Dict[str, str]:
    return {
        "X-Dynamic-Sidecar-Request-DNS": "",
        "X-Dynamic-Sidecar-Request-Scheme": "",
    }


@pytest.fixture
def mocked_director_v0_service_api(
    minimal_app: FastAPI, service: Dict[str, Any], service_labels: Dict[str, Any]
):
    with respx.mock(
        base_url=minimal_app.state.settings.director_v0.base_url(include_tag=False),
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # get services labels
        respx_mock.get(
            f"/v0/services/{urllib.parse.quote_plus(service['key'])}/{service['version']}:labels",
            name="service labels",
        ).respond(json={"data": service_labels})

        yield respx_mock


ServiceParams = namedtuple("ServiceParams", "service, service_labels, exp_status_code")


@pytest.mark.parametrize(
    "service,service_labels, exp_status_code",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreService.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            ),
            id="legacy service",
        ),
        # pytest.param(
        #     *ServiceParams(
        #         service=DynamicServiceCreate.Config.schema_extra["example"],
        #         service_labels=SimcoreService.Config.schema_extra["examples"][1],
        #         exp_status_code=status.HTTP_201_CREATED,
        #     ),
        #     id="dynamic sidecar service",
        # ),
        # pytest.param(
        #     *ServiceParams(
        #         service=DynamicServiceCreate.Config.schema_extra["example"],
        #         service_labels=SimcoreService.Config.schema_extra["examples"][2],
        #         exp_status_code=status.HTTP_201_CREATED,
        #     ),
        #     id="dynamic sidecar service with compose spec",
        # ),
    ],
)
def test_create_dynamic_services(
    mocked_director_v0_service_api,
    client: TestClient,
    dynamic_sidecar_headers: Dict[str, str],
    service: Dict[str, Any],
    exp_status_code: int,
):
    url = URL("/v2/dynamic_services")

    body = DynamicServiceCreate(**service)

    response = client.post(str(url), headers=dynamic_sidecar_headers, data=body.json())
    assert (
        response.status_code == exp_status_code
    ), f"expected status code {exp_status_code}, received {response.status_code}: {response.text}"

    if exp_status_code == status.HTTP_307_TEMPORARY_REDIRECT:
        # check redirection header goes to director-v0
        assert "location" in response.headers
        redirect_url = URL(response.headers["location"])
        assert redirect_url.host == "director"
        assert redirect_url.path == "/v0/running_interactive_services"
        assert redirect_url.params["user_id"] == str(service["user_id"])
        assert redirect_url.params["project_id"] == service["project_id"]
        assert redirect_url.params["service_uuid"] == service["uuid"]
        assert redirect_url.params["service_key"] == service["key"]
        assert redirect_url.params["service_version"] == service["version"]
        assert redirect_url.params["service_basepath"] == service["basepath"]

    if exp_status_code == status.HTTP_201_CREATED:
        # check the returned data
        pass


@pytest.mark.parametrize(
    "service,service_labels, exp_status_code",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreService.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            ),
            id="legacy service",
        ),
        # pytest.param(
        #     *ServiceParams(
        #         service=DynamicServiceCreate.Config.schema_extra["example"],
        #         service_labels=SimcoreService.Config.schema_extra["examples"][1],
        #         exp_status_code=status.HTTP_201_CREATED,
        #     ),
        #     id="dynamic sidecar service",
        # ),
        # pytest.param(
        #     *ServiceParams(
        #         service=DynamicServiceCreate.Config.schema_extra["example"],
        #         service_labels=SimcoreService.Config.schema_extra["examples"][2],
        #         exp_status_code=status.HTTP_201_CREATED,
        #     ),
        #     id="dynamic sidecar service with compose spec",
        # ),
    ],
)
def test_get_service_status(
    mocked_director_v0_service_api,
    client: TestClient,
    service: Dict[str, Any],
    exp_status_code: int,
):
    url = URL(f"/v2/dynamic_services/{service['uuid']}")

    response = client.get(str(url), allow_redirects=False)
    assert (
        response.status_code == exp_status_code
    ), f"expected status code {exp_status_code}, received {response.status_code}: {response.text}"
    if exp_status_code == status.HTTP_307_TEMPORARY_REDIRECT:
        # check redirection header goes to director-v0
        assert "location" in response.headers
        redirect_url = URL(response.headers["location"])
        assert redirect_url.host == "director"
        assert (
            redirect_url.path == f"/v0/running_interactive_services/{service['uuid']}"
        )
        assert redirect_url.params == QueryParams("")  # empty query


@pytest.mark.parametrize(
    "service,service_labels, exp_status_code",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreService.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            ),
            id="legacy service",
        ),
        # pytest.param(
        #     *ServiceParams(
        #         service=DynamicServiceCreate.Config.schema_extra["example"],
        #         service_labels=SimcoreService.Config.schema_extra["examples"][1],
        #         exp_status_code=status.HTTP_201_CREATED,
        #     ),
        #     id="dynamic sidecar service",
        # ),
        # pytest.param(
        #     *ServiceParams(
        #         service=DynamicServiceCreate.Config.schema_extra["example"],
        #         service_labels=SimcoreService.Config.schema_extra["examples"][2],
        #         exp_status_code=status.HTTP_201_CREATED,
        #     ),
        #     id="dynamic sidecar service with compose spec",
        # ),
    ],
)
@pytest.mark.parametrize(
    "save_state,exp_save_state", [(None, True), (True, True), (False, False)]
)
def test_delete_service(
    mocked_director_v0_service_api,
    client: TestClient,
    service: Dict[str, Any],
    exp_status_code: int,
    save_state: Optional[bool],
    exp_save_state: bool,
):

    url = URL(f"/v2/dynamic_services/{service['uuid']}")
    if save_state is not None:
        url = url.copy_with(params={"save_state": save_state})

    response = client.delete(str(url), allow_redirects=False)
    assert (
        response.status_code == exp_status_code
    ), f"expected status code {exp_status_code}, received {response.status_code}: {response.text}"
    if exp_status_code == status.HTTP_307_TEMPORARY_REDIRECT:
        # check redirection header goes to director-v0
        assert "location" in response.headers
        redirect_url = URL(response.headers["location"])
        assert redirect_url.host == "director"
        assert (
            redirect_url.path == f"/v0/running_interactive_services/{service['uuid']}"
        )
        assert redirect_url.params == QueryParams(
            save_state=exp_save_state
        )  # default save_state to True
