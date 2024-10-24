# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member

import asyncio
import re
from typing import Any
from unittest.mock import call

import aiodocker
import arrow
import pytest
from dask_task_models_library.container_tasks.protocol import (
    ContainerCommands,
    ContainerEnvsDict,
    ContainerImage,
    ContainerLabelsDict,
    ContainerTag,
)
from models_library.services_resources import BootMode
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.computational_sidecar.docker_utils import (
    _try_parse_progress,
    create_container_config,
    managed_container,
)
from simcore_service_dask_sidecar.computational_sidecar.models import PROGRESS_REGEXP


@pytest.fixture()
def docker_registry() -> str:
    return "myregistry.local"


@pytest.fixture()
def image() -> str:
    return "myfake/image"


@pytest.fixture()
def tag() -> str:
    return "2.3.45"


@pytest.fixture()
def command() -> list[str]:
    return ["sh", "-c", "some_app"]


@pytest.fixture()
def comp_volume_mount_point() -> str:
    return "/some/fake/entrypoint"


@pytest.mark.parametrize(
    "task_max_resources",
    [{}, {"CPU": 12, "RAM": 2**9}, {"GPU": 4, "RAM": 1**6}],
    ids=lambda x: f"task_resources={x}",
)
@pytest.mark.parametrize("boot_mode", list(BootMode), ids=lambda x: f"bootmode={x}")
@pytest.mark.parametrize(
    "task_envs",
    [{}, {"SOME_ENV": "whatever value that is"}],
    ids=lambda x: f"task_envs={x}",
)
@pytest.mark.parametrize(
    "task_labels",
    [{}, {"some_label": "some_label value"}],
    ids=lambda x: f"task_labels={x}",
)
async def test_create_container_config(
    docker_registry: str,
    image: ContainerImage,
    tag: ContainerTag,
    command: ContainerCommands,
    comp_volume_mount_point: str,
    boot_mode: BootMode,
    task_max_resources: dict[str, Any],
    task_envs: ContainerEnvsDict,
    task_labels: ContainerLabelsDict,
):
    container_config = await create_container_config(
        docker_registry=docker_registry,
        image=image,
        tag=tag,
        command=command,
        comp_volume_mount_point=comp_volume_mount_point,
        boot_mode=boot_mode,
        task_max_resources=task_max_resources,
        envs=task_envs,
        labels=task_labels,
    )
    assert container_config.model_dump(by_alias=True) == (
        {
            "Env": [
                "INPUT_FOLDER=/inputs",
                "OUTPUT_FOLDER=/outputs",
                "LOG_FOLDER=/logs",
                f"SC_COMP_SERVICES_SCHEDULED_AS={boot_mode.value}",
                f"SIMCORE_NANO_CPUS_LIMIT={task_max_resources.get('CPU', 1) * 1e9:.0f}",
                f"SIMCORE_MEMORY_BYTES_LIMIT={task_max_resources.get('RAM', 1024 ** 3)}",
                *[f"{env_var}={env_value}" for env_var, env_value in task_envs.items()],
            ],
            "Cmd": command,
            "Image": f"{docker_registry}/{image}:{tag}",
            "Labels": task_labels,
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


@pytest.mark.parametrize("with_timestamp", [True, False], ids=str)
@pytest.mark.parametrize(
    "log_line, expected_progress_value, progress_regexp",
    [
        ("hello from the logs", None, PROGRESS_REGEXP),
        (
            "[PROGRESS] this is some whatever progress without number",
            None,
            PROGRESS_REGEXP,
        ),
        ("[PROGRESS] .34", 0.34, PROGRESS_REGEXP),
        ("Progress: this is some progress", None, PROGRESS_REGEXP),
        ("PROGRESS: .34", 0.34, PROGRESS_REGEXP),
        ("PROGRESS: 44 percent done", 0.44, PROGRESS_REGEXP),
        ("44 percent done", 0.44, PROGRESS_REGEXP),
        ("PROGRESS: 44/150", 44.0 / 150.0, PROGRESS_REGEXP),
        ("PROGRESS: 44/150...", 44.0 / 150.0, PROGRESS_REGEXP),
        ("any kind of message even with progress inside", None, PROGRESS_REGEXP),
        ("[PROGRESS]1.000000\n", 1.00, PROGRESS_REGEXP),
        ("[PROGRESS] 1\n", 1.00, PROGRESS_REGEXP),
        ("[PROGRESS] 0\n", 0.00, PROGRESS_REGEXP),
        (
            "[PROGRESS]: 1% [ 10 / 624 ] Time Update, estimated remaining time 1 seconds @ 26.43 MCells/s",
            0.01,
            PROGRESS_REGEXP,
        ),
        ("[warn]: this is some warning", None, PROGRESS_REGEXP),
        ("err: this is some error", None, PROGRESS_REGEXP),
        (
            "progress: 10/0 asd this is a 15% 10/asdf progress without progress it will not break the system",
            None,
            PROGRESS_REGEXP,
        ),
        (
            "[PROGRESS]: 21% [ 1219946 / 5545233 ] Assembling matrix",
            0.21,
            re.compile(
                "^(?:\\[?PROGRESS\\]?:?)?\\s*(?P<value>[0-1]?\\.\\d+|\\d+\\s*(?P<percent_sign>%))"
            ),
        ),
    ],
)
async def test__try_parse_progress(
    with_timestamp: bool,
    log_line: str,
    expected_progress_value: float,
    progress_regexp: re.Pattern[str],
):
    expected_time_stamp = arrow.utcnow().datetime
    if with_timestamp:
        log_line = f"{expected_time_stamp.isoformat()} {log_line}"

    received_progress = await _try_parse_progress(
        log_line, progress_regexp=progress_regexp
    )
    assert received_progress == expected_progress_value


@pytest.mark.parametrize(
    "exception_type",
    [
        KeyError("testkey"),
        asyncio.CancelledError("testcancel"),
        aiodocker.DockerError(status=404, data={"message": None}),
    ],
    ids=str,
)
async def test_managed_container_always_removes_container(
    docker_registry: str,
    image: ContainerImage,
    tag: ContainerTag,
    command: ContainerCommands,
    comp_volume_mount_point: str,
    mocker: MockerFixture,
    exception_type: Exception,
):
    container_config = await create_container_config(
        docker_registry=docker_registry,
        image=image,
        tag=tag,
        command=command,
        comp_volume_mount_point=comp_volume_mount_point,
        boot_mode=BootMode.CPU,
        task_max_resources={},
        envs={},
        labels={},
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
                            container_config.model_dump(by_alias=True), name=None
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
    image: ContainerImage,
    tag: ContainerTag,
    command: ContainerCommands,
    comp_volume_mount_point: str,
    mocker: MockerFixture,
):
    container_config = await create_container_config(
        docker_registry=docker_registry,
        image=image,
        tag=tag,
        command=command,
        comp_volume_mount_point=comp_volume_mount_point,
        boot_mode=BootMode.CPU,
        task_max_resources={},
        envs={},
        labels={},
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
