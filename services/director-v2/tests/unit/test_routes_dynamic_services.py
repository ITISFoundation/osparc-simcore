# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import json
import urllib
from collections import namedtuple
from typing import Any, Dict, Optional

import pytest
import respx
from fastapi import FastAPI
from httpx import URL, QueryParams
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.models.domains.dynamic_services import (
    DynamicServiceCreate,
)
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
)
from simcore_service_director_v2.modules.dynamic_sidecar.client_api import (
    setup_api_client,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarNotFoundError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    setup_scheduler,
)
from starlette import status
from starlette.testclient import TestClient

ServiceParams = namedtuple("ServiceParams", "service, service_labels, exp_status_code")


@pytest.fixture
def minimal_config(project_env_devel_environment, monkeypatch) -> None:
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("SC_BOOT_MODE", "default")
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
        base_url=minimal_app.state.settings.DIRECTOR_V0.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # get services labels
        respx_mock.get(
            f"/services/{urllib.parse.quote_plus(service['key'])}/{service['version']}/labels",
            name="service labels",
        ).respond(json={"data": service_labels})

        respx_mock.get(
            f"/running_interactive_services/{service['node_uuid']}",
            name="running interactive service",
        ).respond(json={"data": {}})

        yield respx_mock


@pytest.fixture
def mocked_director_v2_scheduler(mocker: MockerFixture, exp_status_code: int) -> None:
    """because the monitor is disabled some functionality needs to be mocked"""

    # MOCKING get_stack_status
    def get_stack_status(node_uuid: NodeID) -> RunningDynamicServiceDetails:
        if exp_status_code == status.HTTP_307_TEMPORARY_REDIRECT:
            raise DynamicSidecarNotFoundError(node_uuid)

        return RunningDynamicServiceDetails.parse_obj(
            RunningDynamicServiceDetails.Config.schema_extra["examples"][0]
        )

    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler.task.DynamicSidecarsScheduler.get_stack_status",
        side_effect=get_stack_status,
    )

    # MOCKING remove_service
    def remove_service(node_uuid: NodeID, save_state: Optional[bool]) -> None:
        if exp_status_code == status.HTTP_307_TEMPORARY_REDIRECT:
            raise DynamicSidecarNotFoundError(node_uuid)

    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler.task.DynamicSidecarsScheduler.remove_service",
        side_effect=remove_service,
    )


@pytest.mark.parametrize(
    "service, service_labels, exp_status_code",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            ),
            id="LEGACY",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][1],
                exp_status_code=status.HTTP_201_CREATED,
            ),
            id="DYNAMIC",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][2],
                exp_status_code=status.HTTP_201_CREATED,
            ),
            id="DYNAMIC_COMPOSE",
        ),
    ],
)
async def test_create_dynamic_services(
    minimal_config: None,
    mocked_director_v0_service_api,
    async_docker_swarm: None,
    mocked_director_v2_scheduler: None,
    client: TestClient,
    dynamic_sidecar_headers: Dict[str, str],
    service: Dict[str, Any],
    exp_status_code: int,
):
    # dynamic-sidecar components
    await setup_scheduler(client.app)
    await setup_api_client(client.app)

    post_data = DynamicServiceCreate(**service)

    response = client.post(
        "/v2/dynamic_services",
        headers=dynamic_sidecar_headers,
        json=json.loads(post_data.json()),
    )
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
        assert redirect_url.params["service_uuid"] == service["node_uuid"]
        assert redirect_url.params["service_key"] == service["key"]
        assert redirect_url.params["service_version"] == service["version"]
        assert redirect_url.params["service_basepath"] == service["basepath"]

    if exp_status_code == status.HTTP_201_CREATED:
        # check the returned data
        pass


@pytest.mark.parametrize(
    "service, service_labels, exp_status_code",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            ),
            id="LEGACY",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][1],
                exp_status_code=status.HTTP_200_OK,
            ),
            id="DYNAMIC",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][2],
                exp_status_code=status.HTTP_200_OK,
            ),
            id="DYNAMIC_COMPOSE",
        ),
    ],
)
async def test_get_service_status(
    mocked_director_v0_service_api,
    mocked_director_v2_scheduler: None,
    client: TestClient,
    service: Dict[str, Any],
    exp_status_code: int,
):
    # dynamic-sidecar components
    await setup_scheduler(client.app)

    url = URL(f"/v2/dynamic_services/{service['node_uuid']}")

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
            redirect_url.path
            == f"/v0/running_interactive_services/{service['node_uuid']}"
        )
        assert redirect_url.params == QueryParams("")  # empty query


@pytest.mark.parametrize(
    "service, service_labels, exp_status_code",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            ),
            id="LEGACY",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][1],
                exp_status_code=status.HTTP_204_NO_CONTENT,
            ),
            id="DYNAMIC",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][2],
                exp_status_code=status.HTTP_204_NO_CONTENT,
            ),
            id="DYNAMIC_COMPOSE",
        ),
    ],
)
@pytest.mark.parametrize(
    "save_state, exp_save_state", [(None, True), (True, True), (False, False)]
)
async def test_delete_service(
    mocked_director_v0_service_api,
    mocked_director_v2_scheduler: None,
    client: TestClient,
    service: Dict[str, Any],
    exp_status_code: int,
    save_state: Optional[bool],
    exp_save_state: bool,
):
    # dynamic-sidecar components
    await setup_scheduler(client.app)

    url = URL(f"/v2/dynamic_services/{service['node_uuid']}")
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
            redirect_url.path
            == f"/v0/running_interactive_services/{service['node_uuid']}"
        )
        assert redirect_url.params == QueryParams(save_state=exp_save_state)
