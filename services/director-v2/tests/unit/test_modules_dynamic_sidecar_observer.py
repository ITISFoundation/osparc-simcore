# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData
from simcore_service_director_v2.modules.dynamic_sidecar.api_client import (
    setup,
    shutdown,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import (
    DynamicSidecarsScheduler,
    setup_scheduler,
    shutdown_scheduler,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._observer import (
    _apply_observation_cycle,
)


@pytest.fixture
def disable_observation(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._task.DynamicSidecarsScheduler.start",
        autospec=True,
    )


@pytest.fixture
def mock_are_sidecar_and_proxy_services_present(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._observer.are_sidecar_and_proxy_services_present",
        autospec=True,
        return_value=False,
    )


@pytest.fixture
def mock_events(mocker: MockerFixture) -> None:
    for event_to_mock in (
        "CreateSidecars",
        "WaitForSidecarAPI",
        "UpdateHealth",
        "GetStatus",
        "PrepareServicesEnvironment",
        "CreateUserServices",
        "AttachProjectsNetworks",
        "RemoveUserCreatedServices",
    ):
        mocker.patch(
            f"simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._events.{event_to_mock}.action",
            autospec=True,
            return_value=True,
        )


@pytest.fixture
def mock_env(
    disable_postgres: None,
    docker_swarm: None,
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            "SIMCORE_SERVICES_NETWORK_NAME": "test_network",
            "DIRECTOR_HOST": "mocked_out",
            "DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED": "true",
            "S3_ENDPOINT": faker.url(),
            "S3_ACCESS_KEY": faker.pystr(),
            "S3_REGION": faker.pystr(),
            "S3_SECRET_KEY": faker.pystr(),
            "S3_BUCKET_NAME": faker.pystr(),
        },
    )


@pytest.fixture
def mocked_app(mock_env: None) -> FastAPI:
    app = FastAPI()
    app.state.settings = AppSettings.create_from_envs()
    app.state.rabbitmq_client = AsyncMock()
    return app


@pytest.fixture
async def dynamic_sidecar_scheduler(
    mocked_app: FastAPI,
) -> AsyncIterator[DynamicSidecarsScheduler]:
    await setup_scheduler(mocked_app)
    await setup(mocked_app)

    yield mocked_app.state.dynamic_sidecar_scheduler

    await shutdown_scheduler(mocked_app)
    await shutdown(mocked_app)


def _is_observation_task_present(
    dynamic_sidecar_scheduler,
    scheduler_data_from_http_request,
) -> bool:
    return (
        scheduler_data_from_http_request.service_name
        in dynamic_sidecar_scheduler.scheduler._service_observation_task  # noqa: SLF001
    )


@pytest.mark.parametrize("can_save", [False, True])
async def test_regression_break_endless_loop_cancellation_edge_case(
    disable_observation: None,
    mock_are_sidecar_and_proxy_services_present: None,
    mock_events: None,
    dynamic_sidecar_scheduler: DynamicSidecarsScheduler,
    scheduler_data_from_http_request: SchedulerData,
    can_save: bool | None,
):
    # in this situation the scheduler would never end loops forever
    await dynamic_sidecar_scheduler.scheduler.add_service_from_scheduler_data(
        scheduler_data_from_http_request
    )

    # simulate edge case
    scheduler_data_from_http_request.dynamic_sidecar.were_containers_created = True

    assert (
        _is_observation_task_present(
            dynamic_sidecar_scheduler, scheduler_data_from_http_request
        )
        is False
    )

    # NOTE: this will create the observation task as well!
    # Simulates user action like going back to the dashboard.
    await dynamic_sidecar_scheduler.mark_service_for_removal(
        scheduler_data_from_http_request.node_uuid, can_save=can_save
    )

    assert (
        _is_observation_task_present(
            dynamic_sidecar_scheduler, scheduler_data_from_http_request
        )
        is True
    )

    # requires an extra pass to remove the service
    for _ in range(3):
        await _apply_observation_cycle(
            dynamic_sidecar_scheduler, scheduler_data_from_http_request
        )

    assert (
        _is_observation_task_present(
            dynamic_sidecar_scheduler, scheduler_data_from_http_request
        )
        is False
    )
