# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import logging
from typing import Final, Iterable

import pytest
from fastapi import FastAPI
from pydantic import PositiveFloat, PositiveInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.exception_utils import _SKIPS_MESSAGE
from simcore_service_director_v2.models.dynamic_services_scheduler import (
    ContainerState,
    DockerContainerInspect,
    DockerStatus,
)
from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
from simcore_service_director_v2.modules.dynamic_sidecar.api_client import (
    BaseClientHTTPError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core import _events

NETWORK_TOLERANCE_S: Final[PositiveFloat] = 0.1
STEPS: Final[PositiveFloat] = 10
SLEEP_BETWEEN_CALLS: Final[PositiveFloat] = NETWORK_TOLERANCE_S / STEPS
REPEAT_COUNT: Final[PositiveInt] = STEPS + 1


@pytest.fixture
def mock_env(
    disable_postgres: None,
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            "S3_ENDPOINT": "",
            "S3_ACCESS_KEY": "",
            "S3_SECRET_KEY": "",
            "S3_BUCKET_NAME": "",
            "S3_SECURE": "false",
            "POSTGRES_HOST": "",
            "POSTGRES_USER": "",
            "POSTGRES_PASSWORD": "",
            "POSTGRES_DB": "",
            "DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S": f"{NETWORK_TOLERANCE_S}",
        },
    )


@pytest.fixture
def mock_sidecars_client_always_fail(mocker: MockerFixture) -> None:
    class MockedObj:
        @classmethod
        async def containers_inspect(cls, *args, **kwargs) -> None:
            raise BaseClientHTTPError("will always fail")

    mocker.patch.object(_events, "get_sidecars_client", return_value=MockedObj())


@pytest.fixture
def mock_sidecars_client_stops_failing(mocker: MockerFixture) -> None:
    class MockedObj:
        def __init__(self) -> None:
            self.counter = 0

        async def containers_inspect(self, *args, **kwargs) -> None:
            self.counter += 1
            if self.counter < STEPS / 2:
                raise BaseClientHTTPError("will always fail")

    mocker.patch.object(_events, "get_sidecars_client", return_value=MockedObj())


@pytest.fixture
def docker_container_inspect() -> DockerContainerInspect:
    return DockerContainerInspect(
        status=DockerStatus.dead, container_state=ContainerState(**{}), name="", id=""
    )


@pytest.fixture
def scheduler_data(
    scheduler_data: SchedulerData, docker_container_inspect: DockerContainerInspect
) -> SchedulerData:
    scheduler_data.dynamic_sidecar.containers_inspect = [docker_container_inspect]
    return scheduler_data


@pytest.fixture()
def caplog_debug(
    caplog: pytest.LogCaptureFixture,
) -> Iterable[pytest.LogCaptureFixture]:
    with caplog.at_level(
        logging.DEBUG,
    ):
        yield caplog


async def test_event_get_status_network_connectivity(
    mock_sidecars_client_always_fail: None,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    caplog_debug: pytest.LogCaptureFixture,
):
    caplog_debug.clear()
    with pytest.raises(BaseClientHTTPError):
        for _ in range(REPEAT_COUNT):
            await _events.GetStatus.action(minimal_app, scheduler_data)
            await asyncio.sleep(SLEEP_BETWEEN_CALLS)

    assert caplog_debug.text.count(_SKIPS_MESSAGE) > 1


async def test_event_get_status_recovers_after_error(
    mock_sidecars_client_stops_failing: None,
    minimal_app: FastAPI,
    scheduler_data: SchedulerData,
    caplog_debug: pytest.LogCaptureFixture,
):
    caplog_debug.clear()
    for _ in range(REPEAT_COUNT):
        await _events.GetStatus.action(minimal_app, scheduler_data)
        await asyncio.sleep(SLEEP_BETWEEN_CALLS)
    assert caplog_debug.text.count(_SKIPS_MESSAGE) >= 1
