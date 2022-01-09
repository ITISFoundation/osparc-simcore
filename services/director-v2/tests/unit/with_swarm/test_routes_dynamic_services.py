# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import logging
import os
import urllib.parse
from argparse import Namespace
from collections import namedtuple
from typing import Any, AsyncIterator, Dict, Optional
from uuid import UUID

import pytest
import respx
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from httpx import URL, QueryParams
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from pytest_mock.plugin import MockerFixture
from respx import MockRouter
from simcore_service_director_v2.models.domains.dynamic_services import (
    DynamicServiceCreate,
    RetrieveDataOutEnveloped,
)
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
)
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    SchedulerData,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarNotFoundError,
)
from starlette import status
from starlette.testclient import TestClient

ServiceParams = namedtuple(
    "ServiceParams", "service, service_labels, exp_status_code, is_legacy"
)

logger = logging.getLogger(__name__)


@pytest.fixture
def minimal_config(project_env_devel_environment, monkeypatch: MonkeyPatch) -> None:
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("SC_BOOT_MODE", "default")
    monkeypatch.setenv("DIRECTOR_ENABLED", "1")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_TRACING", "null")


@pytest.fixture(scope="session")
def dynamic_sidecar_headers() -> Dict[str, str]:
    return {
        "X-Dynamic-Sidecar-Request-DNS": "",
        "X-Dynamic-Sidecar-Request-Scheme": "",
    }


@pytest.fixture(scope="function")
def mock_env(monkeypatch: MonkeyPatch, docker_swarm: None) -> None:
    # Works as below line in docker.compose.yml
    # ${DOCKER_REGISTRY:-itisfoundation}/dynamic-sidecar:${DOCKER_IMAGE_TAG:-latest}

    registry = os.environ.get("DOCKER_REGISTRY", "local")
    image_tag = os.environ.get("DOCKER_IMAGE_TAG", "production")

    image_name = f"{registry}/dynamic-sidecar:{image_tag}"

    logger.warning("Patching to: DYNAMIC_SIDECAR_IMAGE=%s", image_name)
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", image_name)

    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("DIRECTOR_V2_TRACING", "null")

    monkeypatch.setenv("REGISTRY_AUTH", "false")
    monkeypatch.setenv("REGISTRY_USER", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_SSL", "false")

    monkeypatch.setenv("POSTGRES_HOST", "mocked_host")
    monkeypatch.setenv("POSTGRES_USER", "mocked_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_password")
    monkeypatch.setenv("POSTGRES_DB", "mocked_db")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "false")

    monkeypatch.setenv("SC_BOOT_MODE", "production")


@pytest.fixture
async def mock_retrieve_features(
    minimal_app: FastAPI,
    client: TestClient,
    service: Dict[str, Any],
    is_legacy: bool,
    scheduler_data_from_http_request: SchedulerData,
) -> AsyncIterator[Optional[MockRouter]]:
    with respx.mock(
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        if is_legacy:
            service_details = RunningDynamicServiceDetails.parse_obj(
                RunningDynamicServiceDetails.Config.schema_extra["examples"][0]
            )
            respx_mock.post(
                f"{service_details.legacy_service_url}/retrieve", name="retrieve"
            ).respond(json=RetrieveDataOutEnveloped.Config.schema_extra["examples"][0])

            yield respx_mock
            # no cleanup required
        else:
            dynamic_sidecar_scheduler = minimal_app.state.dynamic_sidecar_scheduler
            node_uuid = UUID(service["node_uuid"])
            serice_name = "serice_name"

            # pylint: disable=protected-access
            dynamic_sidecar_scheduler._inverse_search_mapping[node_uuid] = serice_name
            dynamic_sidecar_scheduler._to_observe[serice_name] = Namespace(
                scheduler_data=scheduler_data_from_http_request
            )

            respx_mock.post(
                f"{scheduler_data_from_http_request.dynamic_sidecar.endpoint}/v1/containers/ports/inputs:pull",
                name="service_pull_input_ports",
            ).respond(json=42)

            yield respx_mock

            dynamic_sidecar_scheduler._inverse_search_mapping.pop(node_uuid)
            dynamic_sidecar_scheduler._to_observe.pop(serice_name)


@pytest.fixture
def mocked_director_v0_service_api(
    minimal_app: FastAPI, service: Dict[str, Any], service_labels: Dict[str, Any]
) -> MockRouter:
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
        ).respond(
            json={
                "data": RunningDynamicServiceDetails.Config.schema_extra["examples"][0]
            }
        )

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
    def remove_service(node_uuid: NodeID, can_save: Optional[bool]) -> None:
        if exp_status_code == status.HTTP_307_TEMPORARY_REDIRECT:
            raise DynamicSidecarNotFoundError(node_uuid)

    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler.task.DynamicSidecarsScheduler.mark_service_for_removal",
        side_effect=remove_service,
    )


@pytest.mark.parametrize(
    "service, service_labels, exp_status_code, is_legacy",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                is_legacy=True,
            ),
            id="LEGACY",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][1],
                exp_status_code=status.HTTP_201_CREATED,
                is_legacy=False,
            ),
            id="DYNAMIC",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][2],
                exp_status_code=status.HTTP_201_CREATED,
                is_legacy=False,
            ),
            id="DYNAMIC_COMPOSE",
        ),
    ],
)
def test_create_dynamic_services(
    minimal_config: None,
    mocked_director_v0_service_api: MockRouter,
    docker_swarm: None,
    mocked_director_v2_scheduler: None,
    client: TestClient,
    dynamic_sidecar_headers: Dict[str, str],
    service: Dict[str, Any],
    exp_status_code: int,
    is_legacy: bool,
):
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
        assert redirect_url.params["service_tag"] == service["version"]
        assert redirect_url.params["service_basepath"] == service["basepath"]

    if exp_status_code == status.HTTP_201_CREATED:
        # check the returned data
        pass


@pytest.mark.parametrize(
    "service, service_labels, exp_status_code, is_legacy",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                is_legacy=True,
            ),
            id="LEGACY",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][1],
                exp_status_code=status.HTTP_200_OK,
                is_legacy=False,
            ),
            id="DYNAMIC",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][2],
                exp_status_code=status.HTTP_200_OK,
                is_legacy=False,
            ),
            id="DYNAMIC_COMPOSE",
        ),
    ],
)
def test_get_service_status(
    mocked_director_v0_service_api: MockRouter,
    mocked_director_v2_scheduler: None,
    client: TestClient,
    service: Dict[str, Any],
    exp_status_code: int,
    is_legacy: bool,
):
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
    "service, service_labels, exp_status_code, is_legacy",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                is_legacy=True,
            ),
            id="LEGACY",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][1],
                exp_status_code=status.HTTP_204_NO_CONTENT,
                is_legacy=False,
            ),
            id="DYNAMIC",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][2],
                exp_status_code=status.HTTP_204_NO_CONTENT,
                is_legacy=False,
            ),
            id="DYNAMIC_COMPOSE",
        ),
    ],
)
@pytest.mark.parametrize(
    "can_save, exp_save_state", [(None, True), (True, True), (False, False)]
)
def test_delete_service(
    mocked_director_v0_service_api: MockRouter,
    mocked_director_v2_scheduler: None,
    client: TestClient,
    service: Dict[str, Any],
    exp_status_code: int,
    is_legacy: bool,
    can_save: Optional[bool],
    exp_save_state: bool,
):
    url = URL(f"/v2/dynamic_services/{service['node_uuid']}")
    if can_save is not None:
        url = url.copy_with(params={"can_save": can_save})

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
        assert redirect_url.params == QueryParams(can_save=exp_save_state)


@pytest.mark.parametrize(
    "service, service_labels, exp_status_code, is_legacy",
    [
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][0],
                exp_status_code=status.HTTP_200_OK,
                is_legacy=True,
            ),
            id="LEGACY",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][1],
                exp_status_code=status.HTTP_200_OK,
                is_legacy=False,
            ),
            id="DYNAMIC",
        ),
        pytest.param(
            *ServiceParams(
                service=DynamicServiceCreate.Config.schema_extra["example"],
                service_labels=SimcoreServiceLabels.Config.schema_extra["examples"][2],
                exp_status_code=status.HTTP_200_OK,
                is_legacy=False,
            ),
            id="DYNAMIC_COMPOSE",
        ),
    ],
)
def test_retrieve(
    mock_retrieve_features: Optional[MockRouter],
    mocked_director_v0_service_api: MockRouter,
    mocked_director_v2_scheduler: None,
    client: TestClient,
    service: Dict[str, Any],
    exp_status_code: int,
    is_legacy: bool,
) -> None:
    url = URL(f"/v2/dynamic_services/{service['node_uuid']}:retrieve")
    response = client.post(str(url), json=dict(port_keys=[]), allow_redirects=False)
    assert (
        response.status_code == exp_status_code
    ), f"expected status code {exp_status_code}, received {response.status_code}: {response.text}"
    assert (
        response.json() == RetrieveDataOutEnveloped.Config.schema_extra["examples"][0]
    )
