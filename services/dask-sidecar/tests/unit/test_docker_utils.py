# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member

import asyncio
import logging
from typing import Any
from unittest.mock import call

import aiodocker
import arrow
import pytest
from models_library.services_resources import BootMode
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.computational_sidecar.docker_utils import (
    LogType,
    _parse_line,
    create_container_config,
    managed_container,
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
    "version1_logs",
    [True, False],
    ids=lambda id: f"version{'>=1' if id is True else '0'}-logs",
)
@pytest.mark.parametrize(
    "log_line, expected_log_type, expected_message, expected_log_level",
    [
        ("hello from the logs", LogType.LOG, "hello from the logs", logging.INFO),
        (
            "[progress] this is some whatever progress without number",
            LogType.LOG,
            "[progress] this is some whatever progress without number",
            logging.INFO,
        ),
        ("[Progress] 34%", LogType.PROGRESS, "0.34", logging.INFO),
        ("[PROGRESS] .34", LogType.PROGRESS, "0.34", logging.INFO),
        ("[progress] 0.44", LogType.PROGRESS, "0.44", logging.INFO),
        ("[progress] 44 percent done", LogType.PROGRESS, "0.44", logging.INFO),
        ("[progress] 44/150", LogType.PROGRESS, f"{(44.0 / 150.0):.2f}", logging.INFO),
        (
            "Progress: this is some progress",
            LogType.LOG,
            "Progress: this is some progress",
            logging.INFO,
        ),
        (
            "progress: 34%",
            LogType.PROGRESS,
            "0.34",
            logging.INFO,
        ),
        ("PROGRESS: .34", LogType.PROGRESS, "0.34", logging.INFO),
        ("progress: 0.44", LogType.PROGRESS, "0.44", logging.INFO),
        ("progress: 44 percent done", LogType.PROGRESS, "0.44", logging.INFO),
        ("44 percent done", LogType.PROGRESS, "0.44", logging.INFO),
        ("progress: 44/150", LogType.PROGRESS, f"{(44.0/150.0):.2f}", logging.INFO),
        ("progress: 44/150...", LogType.PROGRESS, f"{(44.0/150.0):.2f}", logging.INFO),
        (
            "any kind of message even with progress inside",
            LogType.LOG,
            "any kind of message even with progress inside",
            logging.INFO,
        ),
        ("[PROGRESS]1.000000\n", LogType.PROGRESS, "1.00", logging.INFO),
        ("[PROGRESS] 1\n", LogType.PROGRESS, "1.00", logging.INFO),
        ("[PROGRESS] 0\n", LogType.PROGRESS, "0.00", logging.INFO),
        (
            "[PROGRESS]: 1% [ 10 / 624 ] Time Update, estimated remaining time 1 seconds @ 26.43 MCells/s",
            LogType.PROGRESS,
            "0.01",
            logging.INFO,
        ),
        (
            "[warn]: this is some warning",
            LogType.LOG,
            "[warn]: this is some warning",
            logging.WARNING,
        ),
        (
            "err: this is some error",
            LogType.LOG,
            "err: this is some error",
            logging.ERROR,
        ),
    ],
)
async def test_parse_line(
    version1_logs: bool,
    log_line: str,
    expected_log_type: LogType,
    expected_message: str,
    expected_log_level: int,
):
    expected_time_stamp = arrow.utcnow().datetime
    if version1_logs:
        # from version 1 the logs come directly from ```docker logs -t -f``` and contain the timestamp
        # version 0 does not contain a timestamp and is added at parsing time
        log_line = f"{expected_time_stamp.isoformat()} {log_line}"

    (
        received_log_type,
        received_time_stamp,
        received_message,
        received_log_level,
    ) = await _parse_line(log_line)
    assert received_log_type == expected_log_type
    assert received_message == expected_message
    assert received_log_level == expected_log_level
    if version1_logs:
        assert received_time_stamp == expected_time_stamp
    else:
        # in version 0 the time stamps are expected to increase slowly
        assert received_time_stamp >= expected_time_stamp


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


async def test_managed_container_with_broken_container_raises_docker_exception(
    docker_registry: str,
    service_key: str,
    service_version: str,
    command: list[str],
    comp_volume_mount_point: str,
    mocker: MockerFixture,
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
    mocked_aiodocker.return_value.__aenter__.return_value.containers.create.return_value.delete.side_effect = aiodocker.DockerError(
        "bad", {"message": "pytest fake bad message"}
    )
    async with aiodocker.Docker() as docker_client:
        with pytest.raises(aiodocker.DockerError, match="pytest fake bad message"):
            async with managed_container(
                docker_client=docker_client, config=container_config
            ) as container:
                assert container is not None
