# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import asyncio
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerNodeID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from settings_library.redis import RedisSettings
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._public import (
    SidecarsClient,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core import (
    _events_utils,
    _observer,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._abc import (
    DynamicSchedulerEvent,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._events import (
    REGISTERED_EVENTS,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._task import (
    DynamicSidecarsScheduler,
)

pytest_simcore_core_services_selection = [
    "redis",
]

SCHEDULER_INTERVAL_SECONDS: Final[float] = 0.1


@pytest.fixture
def mock_env(
    disable_postgres: None,
    disable_rabbitmq: None,
    mock_env: EnvVarsDict,
    redis_service: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
    simcore_services_network_name: str,
    docker_swarm: None,
    mock_docker_api: None,
    faker: Faker,
) -> None:
    disabled_services_envs = {
        "S3_ENDPOINT": faker.url(),
        "S3_ACCESS_KEY": faker.pystr(),
        "S3_REGION": faker.pystr(),
        "S3_SECRET_KEY": faker.pystr(),
        "S3_BUCKET_NAME": faker.pystr(),
        "POSTGRES_HOST": "",
        "POSTGRES_USER": "",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_DB": "",
    }
    setenvs_from_dict(monkeypatch, disabled_services_envs)

    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv(
        "DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL",
        f"{SCHEDULER_INTERVAL_SECONDS}",
    )


@pytest.fixture
def scheduler_data(scheduler_data_from_http_request: SchedulerData) -> SchedulerData:
    scheduler_data_from_http_request.dynamic_sidecar.docker_node_id = TypeAdapter(
        DockerNodeID
    ).validate_python("testdockernodeid")
    return scheduler_data_from_http_request


@pytest.fixture
def mock_containers_docker_status(
    scheduler_data: SchedulerData,
) -> Iterator[MockRouter]:
    service_endpoint = scheduler_data.endpoint
    with respx.mock as mock:
        mock.get(
            re.compile(
                rf"^http://{scheduler_data.service_name}:{scheduler_data.port}/v1/containers\?only_status=true"
            ),
            name="containers_docker_status",
        ).mock(httpx.Response(200, json={}))
        mock.get(f"{service_endpoint}/health", name="is_healthy").respond(
            json={"is_healthy": True}
        )

        yield mock


@pytest.fixture
def mock_sidecars_client(mocker: MockerFixture) -> None:
    mocker.patch.object(SidecarsClient, "push_service_output_ports")
    mocker.patch.object(SidecarsClient, "save_service_state")
    mocker.patch.object(SidecarsClient, "stop_service")


@pytest.fixture
def mock_is_dynamic_sidecar_stack_missing(mocker: MockerFixture) -> None:
    async def _return_false(*args, **kwargs) -> bool:
        return False

    mocker.patch.object(
        _observer, "is_dynamic_sidecar_stack_missing", side_effect=_return_false
    )


@pytest.fixture
def scheduler(
    mock_containers_docker_status: MockRouter,
    mock_sidecars_client: None,
    mock_is_dynamic_sidecar_stack_missing: None,
    minimal_app: FastAPI,
) -> DynamicSidecarsScheduler:
    return minimal_app.state.dynamic_sidecar_scheduler


class ACounter:
    def __init__(self, start: int = 0) -> None:
        self.start = start
        self.count = start

    def increment(self) -> None:
        self.count += 1


@pytest.fixture(params=[True, False])
def error_raised_by_saving_state(request: pytest.FixtureRequest) -> bool:
    return request.param  # type: ignore


@dataclass
class UseCase:
    can_save: bool
    wait_for_manual_intervention_after_error: bool
    outcome_service_removed: bool


@pytest.fixture(
    params=[
        UseCase(
            can_save=False,
            wait_for_manual_intervention_after_error=False,
            outcome_service_removed=True,
        ),
        UseCase(
            can_save=False,
            wait_for_manual_intervention_after_error=True,
            outcome_service_removed=False,
        ),
        UseCase(
            can_save=True,
            wait_for_manual_intervention_after_error=False,
            outcome_service_removed=True,
        ),
        UseCase(
            can_save=True,
            wait_for_manual_intervention_after_error=True,
            outcome_service_removed=False,
        ),
    ]
)
def use_case(request) -> UseCase:
    return request.param  # type: ignore


@pytest.fixture
def mocked_dynamic_scheduler_events(
    error_raised_by_saving_state: bool, use_case: UseCase
) -> ACounter:
    counter = ACounter()

    class AlwaysTriggersDynamicSchedulerEvent(DynamicSchedulerEvent):
        @classmethod
        async def will_trigger(
            cls, app: FastAPI, scheduler_data: SchedulerData
        ) -> bool:
            return True

        @classmethod
        async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
            counter.increment()
            if error_raised_by_saving_state:
                # emulate the error was generated while saving the state
                scheduler_data.dynamic_sidecar.service_removal_state.can_save = (
                    use_case.can_save
                )
                scheduler_data.dynamic_sidecar.wait_for_manual_intervention_after_error = (
                    use_case.wait_for_manual_intervention_after_error
                )
            msg = "Failed as planned"
            raise RuntimeError(msg)

    test_defined_scheduler_events: list[type[DynamicSchedulerEvent]] = [
        AlwaysTriggersDynamicSchedulerEvent
    ]

    # replace REGISTERED EVENTS
    REGISTERED_EVENTS.clear()
    for event in test_defined_scheduler_events:
        REGISTERED_EVENTS.append(event)

    return counter


@pytest.fixture
def mock_rpc_calls(mocker: MockerFixture, minimal_app: FastAPI) -> None:
    minimal_app.state.rabbitmq_rpc_client = AsyncMock()
    mocker.patch.object(_events_utils, "remove_volumes_without_backup_for_service")
    mocker.patch.object(_events_utils, "force_container_cleanup")


@pytest.fixture(params=[True, False])
def node_present_in_db(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture
def mock_projects_repository(mocker: MockerFixture, node_present_in_db: bool) -> None:
    mocked_obj = AsyncMock()
    mocked_obj.is_node_present_in_workbench(return_value=node_present_in_db)

    module_base = "simcore_service_director_v2.modules.dynamic_sidecar.scheduler"
    mocker.patch(
        f"{module_base}._core._events_utils.get_repository", return_value=mocked_obj
    )


async def test_skip_observation_cycle_after_error(
    mock_exclusive: None,
    docker_swarm: None,
    minimal_app: FastAPI,
    mock_projects_repository: None,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: ACounter,
    error_raised_by_saving_state: bool,
    use_case: UseCase,
    mock_rpc_calls: None,
):

    # add a task, emulate an error make sure no observation cycle is
    # being triggered again
    assert mocked_dynamic_scheduler_events.count == 0
    await scheduler.scheduler.add_service_from_scheduler_data(scheduler_data)
    # check it is being tracked
    assert scheduler_data.node_uuid in scheduler.scheduler._inverse_search_mapping

    # ensure observation cycle triggers a lot
    await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS * 10)
    # only expect the event to be triggered once, when it raised
    # an error and no longer trigger again
    assert mocked_dynamic_scheduler_events.count == 1

    # check if service was properly removed or is still kept for manual interventions
    if error_raised_by_saving_state:
        if use_case.outcome_service_removed:
            assert (
                scheduler_data.node_uuid
                not in scheduler.scheduler._inverse_search_mapping
            )
        else:
            assert (
                scheduler_data.node_uuid in scheduler.scheduler._inverse_search_mapping
            )
    else:
        assert (
            scheduler_data.node_uuid not in scheduler.scheduler._inverse_search_mapping
        )
