# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import AsyncIterator

import pytest
import respx
from faker import Faker
from fastapi import status
from httpx import Response
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceCreate
from models_library.basic_types import PortInt
from models_library.service_settings_labels import SimcoreServiceLabels
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarNotFoundError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
)
from starlette.testclient import TestClient


@pytest.fixture
def mock_env(
    mock_exclusive: None,
    disable_rabbitmq: None,
    disable_postgres: None,
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    docker_swarm: None,
    faker: Faker,
) -> None:
    monkeypatch.setenv("SC_BOOT_MODE", "default")
    monkeypatch.setenv("DIRECTOR_ENABLED", "false")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "false")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "false")

    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")

    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())


@pytest.fixture
def dynamic_sidecar_scheduler(client: TestClient) -> DynamicSidecarsScheduler:
    return client.app.state.dynamic_sidecar_scheduler  # type: ignore


@pytest.fixture
def mock_apply_observation_cycle(mocker: MockerFixture) -> None:
    module_base = (
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._observer"
    )
    mocker.patch(f"{module_base}._apply_observation_cycle", autospec=True)


@pytest.fixture
def mock_free_reserved_disk_space(mocker: MockerFixture) -> None:
    module_base = "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._task"
    mocker.patch(
        f"{module_base}.DynamicSidecarsScheduler.free_reserved_disk_space",
        autospec=True,
    )


@pytest.fixture
async def mock_sidecar_api(
    scheduler_data: SchedulerData,
) -> AsyncIterator[None]:
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as respx_mock:
        respx_mock.get(f"{scheduler_data.endpoint}/health", name="is_healthy").respond(
            json={"is_healthy": True}
        )

        yield


@pytest.fixture
async def observed_service(
    dynamic_sidecar_scheduler: DynamicSidecarsScheduler,
    dynamic_service_create: DynamicServiceCreate,
    simcore_service_labels: SimcoreServiceLabels,
    dynamic_sidecar_port: PortInt,
    request_dns: str,
    request_scheme: str,
    can_save: bool,
) -> SchedulerData:
    await dynamic_sidecar_scheduler.add_service(
        service=dynamic_service_create,
        simcore_service_labels=simcore_service_labels,
        port=dynamic_sidecar_port,
        request_dns=request_dns,
        request_scheme=request_scheme,
        request_simcore_user_agent="",
        can_save=can_save,
    )
    return dynamic_sidecar_scheduler.scheduler.get_scheduler_data(
        dynamic_service_create.node_uuid
    )


@pytest.fixture
def mock_scheduler_service_shutdown_tasks(mocker: MockerFixture) -> None:
    module_base = "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._events_utils"
    mocker.patch(f"{module_base}.service_push_outputs", autospec=True)
    mocker.patch(f"{module_base}.service_remove_containers", autospec=True)
    mocker.patch(
        f"{module_base}.service_remove_sidecar_proxy_docker_networks_and_volumes",
        autospec=True,
    )
    mocker.patch(f"{module_base}.service_save_state", autospec=True)


async def test_update_service_observation_node_not_found(
    scheduler_data: SchedulerData, client: TestClient
):
    with pytest.raises(DynamicSidecarNotFoundError):
        client.patch(
            f"/v2/dynamic_scheduler/services/{scheduler_data.node_uuid}/observation",
            json={"is_disabled": False},
        )


async def test_update_service_observation(
    mock_apply_observation_cycle: None,
    mock_sidecar_api: None,
    client: TestClient,
    observed_service: SchedulerData,
):
    def _toggle(*, is_disabled: bool) -> Response:
        return client.patch(
            f"/v2/dynamic_scheduler/services/{observed_service.node_uuid}/observation",
            json={"is_disabled": is_disabled},
        )

    # trying to lock the service
    was_423_detected = False
    was_204_detected = False
    while not was_423_detected and not was_204_detected:
        response = _toggle(is_disabled=True)

        # the service is being observed at regular intervals
        # while the service is being observed an
        # HTTP_423_LOCKED will be returned
        # retrying until the service can be locked

        if response.status_code == status.HTTP_423_LOCKED:
            assert (
                response.json()["errors"][0]
                == f"Could not toggle service {observed_service.node_uuid} observation to disabled=True"
            )
            was_423_detected = True

        if response.status_code == status.HTTP_204_NO_CONTENT:
            assert response.text == ""
            was_204_detected = True

        await asyncio.sleep(0.1)

    # while disabled can always mark it as disabled
    response = _toggle(is_disabled=True)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.text == ""

    # at this point it is always possible to remove the lock
    response = _toggle(is_disabled=False)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.text == ""


@pytest.mark.parametrize(
    "method, route_suffix, task_name",
    [
        ("DELETE", "containers", "_task_remove_service_containers"),
        ("POST", "state:save", "_task_save_service_state"),
        ("POST", "outputs:push", "_task_push_service_outputs"),
        ("DELETE", "docker-resources", "_task_cleanup_service_docker_resources"),
    ],
)
async def test_409_response(
    mock_apply_observation_cycle: None,
    mock_scheduler_service_shutdown_tasks: None,
    client: TestClient,
    observed_service: SchedulerData,
    method: str,
    route_suffix: str,
    task_name: str,
):
    response = client.request(
        method,
        f"/v2/dynamic_scheduler/services/{observed_service.node_uuid}/{route_suffix}",
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    task_id = response.json()
    assert (
        f"simcore_service_director_v2.api.routes.dynamic_scheduler.{task_name}."
        in task_id
    )

    response = client.request(
        method,
        f"/v2/dynamic_scheduler/services/{observed_service.node_uuid}/{route_suffix}",
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "must be unique" in response.text


async def test_free_reserved_disk_space(
    mock_apply_observation_cycle: None,
    mock_free_reserved_disk_space: None,
    client: TestClient,
    observed_service: SchedulerData,
):
    response = client.post(
        f"/v2/dynamic_scheduler/services/{observed_service.node_uuid}/disk/reserved:free",
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
