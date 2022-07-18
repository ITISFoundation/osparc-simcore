# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import re
from typing import Final, Iterator

import httpx
import pytest
import respx
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    SchedulerData,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler.events import (
    REGISTERED_EVENTS,
    DynamicSchedulerEvent,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler.task import (
    DynamicSidecarsScheduler,
)

SCHEDULER_INTERVAL_SECONDS: Final[float] = 0.1

# FIXTURES


@pytest.fixture
def mock_env(
    mock_env: EnvVarsDict,
    monkeypatch: MonkeyPatch,
    simcore_services_network_name: str,
    docker_swarm: None,
    mock_docker_api: None,
) -> None:
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", simcore_services_network_name)
    monkeypatch.setenv("DIRECTOR_HOST", "mocked_out")
    monkeypatch.setenv(
        "DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS",
        f"{SCHEDULER_INTERVAL_SECONDS}",
    )
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "false")
    monkeypatch.setenv("POSTGRES_HOST", "test")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")


@pytest.fixture
def scheduler_data(scheduler_data_from_http_request: SchedulerData) -> SchedulerData:
    return scheduler_data_from_http_request


@pytest.fixture
def mock_containers_docker_status(
    scheduler_data: SchedulerData,
) -> Iterator[MockRouter]:
    service_endpoint = scheduler_data.dynamic_sidecar.endpoint
    with respx.mock as mock:
        mock.get(
            re.compile(
                rf"^http://{scheduler_data.service_name}:{scheduler_data.dynamic_sidecar.port}/v1/containers\?only_status=true"
            ),
            name="containers_docker_status",
        ).mock(httpx.Response(200, json={}))
        mock.get(f"{service_endpoint}/health", name="is_healthy").respond(
            json=dict(is_healthy=True)
        )

        yield mock


@pytest.fixture
def scheduler(
    mock_containers_docker_status: MockRouter, minimal_app: FastAPI
) -> DynamicSidecarsScheduler:
    return minimal_app.state.dynamic_sidecar_scheduler


class ACounter:
    def __init__(self, start: int = 0) -> None:
        self.start = start
        self.count = start

    def increment(self) -> None:
        self.count += 1


@pytest.fixture
def mocked_dynamic_scheduler_events() -> ACounter:
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
            raise RuntimeError("Failed as planned")

    test_defined_scheduler_events: list[type[DynamicSchedulerEvent]] = [
        AlwaysTriggersDynamicSchedulerEvent
    ]

    # replace REGISTERED EVENTS
    REGISTERED_EVENTS.clear()
    for event in test_defined_scheduler_events:
        REGISTERED_EVENTS.append(event)

    return counter


# TESTS


async def test_skip_observation_cycle_after_error(
    minimal_app: FastAPI,
    scheduler: DynamicSidecarsScheduler,
    scheduler_data: SchedulerData,
    mocked_dynamic_scheduler_events: ACounter,
):
    # add a task, emulate an error make sure no observation cycle is
    # being triggered again
    assert mocked_dynamic_scheduler_events.count == 0
    await scheduler.add_service(scheduler_data)

    # ensure observation cycle triggers a lot
    await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS * 10)
    # only expect the event to be triggered once, when it raised
    # an error and no longer trigger again
    assert mocked_dynamic_scheduler_events.count == 1
