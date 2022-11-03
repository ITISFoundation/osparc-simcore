# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member

import asyncio
from typing import Any
from unittest.mock import call

import aiodocker
import pytest
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.boot_mode import BootMode
from simcore_service_dask_sidecar.computational_sidecar.docker_utils import (
    DEFAULT_TIME_STAMP,
    LogType,
    create_container_config,
    managed_container,
    parse_line,
)


@pytest.fixture()
def docker_registry() -> str:
    return "myregistry.local"


@pytest.fixture()
def service_key() -> str:
    return "myfake/service_key"


@pytest.fixture()
def service_version() -> str:
    return "2.3.45"


@pytest.fixture()
def command() -> list[str]:
    return ["sh", "-c", "some_app"]


@pytest.fixture()
def comp_volume_mount_point() -> str:
    return "/some/fake/entrypoint"


@pytest.mark.parametrize(
    "task_max_resources", [{}, {"CPU": 12, "RAM": 2**9}, {"GPU": 4, "RAM": 1**6}]
)
@pytest.mark.parametrize("boot_mode", list(BootMode))
async def test_create_container_config(
    docker_registry: str,
    service_key: str,
    service_version: str,
    command: list[str],
    comp_volume_mount_point: str,
    boot_mode: BootMode,
    task_max_resources: dict[str, Any],
):

    container_config = await create_container_config(
        docker_registry,
        service_key,
        service_version,
        command,
        comp_volume_mount_point,
        boot_mode,
        task_max_resources,
    )
    assert container_config.dict(by_alias=True) == (
        {
            "Env": [
                "INPUT_FOLDER=/inputs",
                "OUTPUT_FOLDER=/outputs",
                "LOG_FOLDER=/logs",
                f"SC_COMP_SERVICES_SCHEDULED_AS={boot_mode.value}",
                f"SIMCORE_NANO_CPUS_LIMIT={task_max_resources.get('CPU', 1) * 1e9:.0f}",
                f"SIMCORE_MEMORY_BYTES_LIMIT={task_max_resources.get('RAM', 1024 ** 3)}",
            ],
            "Cmd": command,
            "Image": f"{docker_registry}/{service_key}:{service_version}",
            "Labels": {},
            "HostConfig": {
                "Binds": [
                    f"{comp_volume_mount_point}/inputs:/inputs",
                    f"{comp_volume_mount_point}/outputs:/outputs",
                    f"{comp_volume_mount_point}/logs:/logs",
                ],
                "Init": True,
                "Memory": task_max_resources.get("RAM", 1024**3),
                "MemorySwap": task_max_resources.get("RAM", 1024**3),
                "NanoCPUs": task_max_resources.get("CPU", 1) * 1e9,
            },
        }
    )


@pytest.mark.parametrize(
    "log_line, expected_parsing",
    [
        (
            "2021-10-05T09:53:48.873236400Z hello from the logs",
            (
                LogType.LOG,
                "2021-10-05T09:53:48.873236400Z",
                "hello from the logs",
            ),
        ),
        (
            "This is not an expected docker log",
            (
                LogType.LOG,
                DEFAULT_TIME_STAMP,
                "This is not an expected docker log",
            ),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [progress] this is some whatever progress without number",
            (
                LogType.LOG,
                "2021-10-05T09:53:48.873236400Z",
                "[progress] this is some whatever progress without number",
            ),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [Progress] 34%",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "0.34"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [PROGRESS] .34",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "0.34"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [progress] 0.44",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "0.44"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [progress] 44 percent done",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "0.44"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [progress] 44/150",
            (
                LogType.PROGRESS,
                "2021-10-05T09:53:48.873236400Z",
                f"{(44.0 / 150.0):.2f}",
            ),
        ),
        (
            "2021-10-05T09:53:48.873236400Z Progress: this is some progress",
            (
                LogType.LOG,
                "2021-10-05T09:53:48.873236400Z",
                "Progress: this is some progress",
            ),
        ),
        (
            "2021-10-05T09:53:48.873236400Z progress: 34%",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "0.34"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z PROGRESS: .34",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "0.34"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z progress: 0.44",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "0.44"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z progress: 44 percent done",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "0.44"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z progress: 44/150",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", f"{(44.0/150.0):.2f}"),
        ),
        (
            "2021-10-05T09:53:48.873236400Z any kind of message even with progress inside",
            (
                LogType.LOG,
                "2021-10-05T09:53:48.873236400Z",
                "any kind of message even with progress inside",
            ),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [PROGRESS]1.000000\n",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "1.00"),
        ),
    ],
)
async def test_parse_line(log_line: str, expected_parsing: tuple[LogType, str, str]):
    assert await parse_line(log_line) == expected_parsing


@pytest.mark.parametrize(
    "exception_type",
    [
        KeyError("testkey"),
        asyncio.CancelledError("testcancel"),
        aiodocker.DockerError(status=404, data={"message": None}),
    ],
)
async def test_managed_container_always_removes_container(
    docker_registry: str,
    service_key: str,
    service_version: str,
    command: list[str],
    comp_volume_mount_point: str,
    mocker: MockerFixture,
    exception_type: Exception,
):
    container_config = await create_container_config(
        docker_registry,
        service_key,
        service_version,
        command,
        comp_volume_mount_point,
        boot_mode=BootMode.CPU,
        task_max_resources={},
    )

    mocked_aiodocker = mocker.patch("aiodocker.Docker", autospec=True)
    async with aiodocker.Docker() as docker_client:
        with pytest.raises(type(exception_type)):
            async with managed_container(
                docker_client=docker_client, config=container_config
            ) as container:
                mocked_aiodocker.assert_has_calls(
                    calls=[
                        call(),
                        call().__aenter__(),
                        call()
                        .__aenter__()
                        .containers.create(
                            container_config.dict(by_alias=True), name=None
                        ),
                    ]
                )
                mocked_aiodocker.reset_mock()
                assert container is not None

                raise exception_type
        # check the container was deleted
        mocked_aiodocker.assert_has_calls(
            calls=[
                call()
                .__aenter__()
                .containers.create()
                .delete(remove=True, v=True, force=True)
            ]
        )
