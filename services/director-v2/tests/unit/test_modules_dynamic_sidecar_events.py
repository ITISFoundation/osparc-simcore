# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from typing import Final

import pytest
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from pydantic import PositiveFloat, PositiveInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    DockerContainerInspect,
    DockerStatus,
)
from simcore_service_director_v2.modules.dynamic_sidecar.api_client import (
    BaseClientHTTPError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler import events

NETWORK_TOLERANCE_S: Final[PositiveFloat] = 0.1
STEPS: Final[PositiveFloat] = 10
SLEEP_BETWEEN_CALLS: Final[PositiveFloat] = NETWORK_TOLERANCE_S / STEPS
REPEAT_COUNT: Final[PositiveInt] = STEPS + 1


@pytest.fixture
def mock_env(
    mock_env: EnvVarsDict,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DYNAMIC_SIDECAR_NETWORK_ISSUES_TOLERANCE_S", f"{NETWORK_TOLERANCE_S}"
    )

    monkeypatch.setenv("S3_ENDPOINT", "")
    monkeypatch.setenv("S3_ACCESS_KEY", "")
    monkeypatch.setenv("S3_SECRET_KEY", "")
    monkeypatch.setenv("S3_BUCKET_NAME", "")
    monkeypatch.setenv("S3_SECURE", "false")
    monkeypatch.setenv("POSTGRES_HOST", "")
    monkeypatch.setenv("POSTGRES_USER", "")
    monkeypatch.setenv("POSTGRES_PASSWORD", "")
    monkeypatch.setenv("POSTGRES_DB", "")


@pytest.fixture
def mock_dynamic_sidecar_client_always_fail(mocker: MockerFixture) -> None:
    class MockedObj:
        @classmethod
        async def containers_inspect(cls, *args, **kwargs) -> None:
            raise BaseClientHTTPError("will always fail")

    mocker.patch.object(events, "get_dynamic_sidecar_client", return_value=MockedObj())


@pytest.fixture
def mock_dynamic_sidecar_client_stops_failing(mocker: MockerFixture) -> None:
    class MockedObj:
        def __init__(self) -> None:
            self.counter = 0

        async def containers_inspect(self, *args, **kwargs) -> None:
            self.counter += 1
            if self.counter < STEPS / 2:
                raise BaseClientHTTPError("will always fail")

    mocker.patch.object(events, "get_dynamic_sidecar_client", return_value=MockedObj())


@pytest.fixture
def docker_container_inspect() -> DockerContainerInspect:
    return DockerContainerInspect(status=DockerStatus.DEAD, name="", id="")


@pytest.fixture
def scheduler_data(
    scheduler_data: SchedulerData, docker_container_inspect: DockerContainerInspect
) -> SchedulerData:
    scheduler_data.dynamic_sidecar.containers_inspect = [docker_container_inspect]
    return scheduler_data


async def test_event_get_status_network_connectivity(
    mock_dynamic_sidecar_client_always_fail: None,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    caplog_info_level: LogCaptureFixture,
):
    with pytest.raises(BaseClientHTTPError):
        for _ in range(REPEAT_COUNT):
            await events.GetStatus.action(minimal_app, scheduler_data)
            await asyncio.sleep(SLEEP_BETWEEN_CALLS)

    assert caplog_info_level.text.count("Could not contact") > 1
    assert caplog_info_level.text.count("It was still not possible to reach") == 1


async def test_event_get_status_recovers_after_error(
    mock_dynamic_sidecar_client_stops_failing: None,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    caplog_info_level: LogCaptureFixture,
):
    for _ in range(REPEAT_COUNT):
        await events.GetStatus.action(minimal_app, scheduler_data)
        await asyncio.sleep(SLEEP_BETWEEN_CALLS)
    assert caplog_info_level.text.count("Could not contact") >= 1
    assert "It was still not possible to reach" not in caplog_info_level.text
