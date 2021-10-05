# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member

from datetime import datetime
from typing import List, Tuple

import pytest
from simcore_service_dask_sidecar.boot_mode import BootMode
from simcore_service_dask_sidecar.computational_sidecar.docker_utils import (
    DEFAULT_TIME_STAMP,
    LogType,
    create_container_config,
    parse_line,
    to_datetime,
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
def command() -> List[str]:
    return ["sh", "-c", "some_app"]


@pytest.fixture()
def comp_volume_mount_point() -> str:
    return "/some/fake/entrypoint"


@pytest.mark.parametrize("boot_mode", [boot for boot in BootMode])
async def test_create_container_config(
    docker_registry: str,
    service_key: str,
    service_version: str,
    command: List[str],
    comp_volume_mount_point: str,
    boot_mode: BootMode,
):

    container_config = await create_container_config(
        docker_registry,
        service_key,
        service_version,
        command,
        comp_volume_mount_point,
        boot_mode,
    )

    assert container_config.dict(by_alias=True) == (
        {
            "Env": [
                "INPUT_FOLDER=/inputs",
                "OUTPUT_FOLDER=/outputs",
                "LOG_FOLDER=/logs",
                f"SC_COMP_SERVICES_SCHEDULED_AS={boot_mode.value}",
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
                "Memory": 1073741824,
                "NanoCPUs": 1000000000,
            },
        }
    )


@pytest.mark.parametrize(
    "docker_time, expected_datetime",
    [("2020-10-09T12:28:14.771034099Z", datetime(2020, 10, 9, 12, 28, 14, 771034))],
)
def test_to_datetime(docker_time: str, expected_datetime: datetime):
    assert to_datetime(docker_time) == expected_datetime


@pytest.mark.parametrize(
    "log_line, expected_parsing",
    [
        (
            "2021-10-05T09:53:48.873236400Z hello from the logs",
            (
                LogType.LOG,
                "2021-10-05T09:53:48.873236400Z",
                "[task] hello from the logs",
            ),
        ),
        (
            "This is not an expected docker log",
            (
                LogType.LOG,
                DEFAULT_TIME_STAMP,
                "[task] This is not an expected docker log",
            ),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [progress] this is some whatever progress without number",
            (
                LogType.LOG,
                "2021-10-05T09:53:48.873236400Z",
                "[task] [progress] this is some whatever progress without number",
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
                "[task] Progress: this is some progress",
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
                "[task] any kind of message even with progress inside",
            ),
        ),
        (
            "2021-10-05T09:53:48.873236400Z [PROGRESS]1.000000\n",
            (LogType.PROGRESS, "2021-10-05T09:53:48.873236400Z", "1.00"),
        ),
    ],
)
async def test_parse_line(log_line: str, expected_parsing: Tuple[LogType, str, str]):
    assert await parse_line(log_line) == expected_parsing
