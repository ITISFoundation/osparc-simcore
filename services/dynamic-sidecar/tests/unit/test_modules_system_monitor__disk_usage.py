# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from common_library.json_serialization import json_dumps
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import (
    DiskUsage,
    MountPathCategory,
)
from models_library.projects_nodes_io import NodeID
from models_library.services_types import RunID
from models_library.users import UserID
from psutil._common import sdiskusage
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes
from simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage import (
    DiskUsageMonitor,
    _get_monitored_paths,
    get_usage,
)


@pytest.fixture
def dy_volumes(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def get_monitored_paths(
    dy_volumes: Path, node_id: NodeID
) -> Callable[[Path, Path, list[Path]], dict[MountPathCategory, set[Path]]]:
    def _(
        inputs: Path, outputs: Path, states: list[Path]
    ) -> dict[MountPathCategory, set[Path]]:
        mounted_volumes = MountedVolumes(
            run_id=RunID.create(),
            node_id=node_id,
            inputs_path=dy_volumes / inputs,
            outputs_path=dy_volumes / outputs,
            user_preferences_path=None,
            state_paths=[dy_volumes / x for x in states],
            state_exclude=set(),
            compose_namespace="",
            dy_volumes=dy_volumes,
        )
        app = Mock()
        app.state = Mock()
        app.state.mounted_volumes = mounted_volumes
        return _get_monitored_paths(app)

    return _


@pytest.fixture
def mock_disk_usage(mocker: MockerFixture) -> Callable[[dict[str, ByteSize]], None]:
    base_module = "simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage"

    def _(free: dict[str, ByteSize]) -> None:
        def _disk_usage(path: str) -> sdiskusage:
            return sdiskusage(total=0, used=0, free=free[path], percent=0)

        mocker.patch(f"{base_module}.psutil.disk_usage", side_effect=_disk_usage)

    return _


@pytest.fixture
def publish_disk_usage_spy(mocker: MockerFixture) -> Mock:
    mock = Mock()

    def __publish_disk_usage(
        app: FastAPI,
        *,
        user_id: UserID,
        node_id: NodeID,
        usage: dict[Path, DiskUsage],
    ) -> None:
        mock(usage)

    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage.publish_disk_usage",
        side_effect=__publish_disk_usage,
    )
    return mock


def _get_entry(mock: Mock, *, index: int) -> dict[Path, DiskUsage]:
    return mock.call_args_list[index].args[0]


def _get_byte_size(byte_size_as_str: str) -> ByteSize:
    return TypeAdapter(ByteSize).validate_python(byte_size_as_str)


def _get_mocked_disk_usage(byte_size_as_str: str) -> DiskUsage:
    bytes_size = _get_byte_size(byte_size_as_str)
    return DiskUsage(
        total=bytes_size, used=ByteSize(0), free=bytes_size, used_percent=0
    )


async def _assert_monitor_triggers(
    disk_usage_monitor: DiskUsageMonitor,
    publish_disk_usage_spy: Mock,
    *,
    expected_events: int,
    monitor_call_count: int = 10,
) -> None:
    for _ in range(monitor_call_count):
        # regardless of how many times it's called only generates 1 publish event
        await disk_usage_monitor._monitor()  # pylint:disable=protected-access  # noqa: SLF001
    assert len(publish_disk_usage_spy.call_args_list) == expected_events


async def test_disk_usage_monitor(
    mock_disk_usage: Callable[[dict[str, ByteSize]], None],
    get_monitored_paths: Callable[
        [Path, Path, list[Path]], dict[MountPathCategory, set[Path]]
    ],
    dy_volumes: Path,
    publish_disk_usage_spy: Mock,
    node_id: NodeID,
) -> None:
    disk_usage_monitor = DiskUsageMonitor(
        app=AsyncMock(),
        user_id=1,
        node_id=node_id,
        interval=timedelta(seconds=5),
        monitored_paths=get_monitored_paths(
            Path("/inputs"), Path("/outputs"), [Path("/workspace")]
        ),
        dy_volumes_mount_dir=dy_volumes,
    )

    assert len(publish_disk_usage_spy.call_args_list) == 0

    for i in range(1, 3):
        mock_disk_usage(
            {
                f"{p}": _get_byte_size(f"{i*2}kb")
                for p in disk_usage_monitor._monitored_paths_set  # noqa: SLF001
            },
        )

        await _assert_monitor_triggers(
            disk_usage_monitor, publish_disk_usage_spy, expected_events=1
        )

        assert _get_entry(publish_disk_usage_spy, index=0) == {
            MountPathCategory.HOST: _get_mocked_disk_usage(f"{i*2}kb"),
        }

        # reset mock to test again
        publish_disk_usage_spy.reset_mock()


def _random_tmp_file(tmp_path: Path, faker: Faker) -> None:
    some_path: Path = tmp_path / f"{faker.uuid4()}"
    some_path.write_text("some text here")


async def test_get_usage(tmp_path: Path, faker: Faker):
    usage_before = await get_usage(Path("/"))
    _random_tmp_file(tmp_path, faker)
    usage_after = await get_usage(Path("/"))

    assert usage_after.free < usage_before.free


async def test_disk_usage_monitor_new_frontend_format(
    mock_disk_usage: Callable[[dict[str, ByteSize]], None],
    get_monitored_paths: Callable[
        [Path, Path, list[Path]], dict[MountPathCategory, set[Path]]
    ],
    publish_disk_usage_spy: Mock,
    node_id: NodeID,
    dy_volumes: Path,
) -> None:
    disk_usage_monitor = DiskUsageMonitor(
        app=AsyncMock(),
        user_id=1,
        node_id=node_id,
        interval=timedelta(seconds=5),
        monitored_paths=get_monitored_paths(
            Path("/home/user/inputs"),
            Path("/home/user/outputs"),
            [Path("/home/user/workspace"), Path("/.data/assets")],
        ),
        dy_volumes_mount_dir=dy_volumes,
    )

    mock_disk_usage(
        {
            f"{p}": ByteSize(1294390525952)
            for p in disk_usage_monitor._monitored_paths_set  # noqa: SLF001
        },
    )

    async def _wait_for_usage() -> dict[str, DiskUsage]:
        publish_disk_usage_spy.reset_mock()
        await disk_usage_monitor._monitor()  # noqa: SLF001
        publish_disk_usage_spy.assert_called()
        return publish_disk_usage_spy.call_args_list[0][0][0]

    # normally only 1 entry is found
    frontend_usage = await _wait_for_usage()
    print(json_dumps(frontend_usage, indent=2))
    assert len(frontend_usage) == 1
    assert MountPathCategory.HOST in frontend_usage
    assert frontend_usage[MountPathCategory.HOST] == _get_mocked_disk_usage(
        "1294390525952"
    )

    # emulate EFS sending metrics, 2 entries are found

    disk_usage_monitor.set_disk_usage_for_path(
        {
            ".data_assets": _get_mocked_disk_usage("1GB"),
            "home_user_workspace": _get_mocked_disk_usage("1GB"),
        }
    )

    frontend_usage = await _wait_for_usage()
    print(json_dumps(frontend_usage, indent=2))
    assert len(frontend_usage) == 2
    assert MountPathCategory.HOST in frontend_usage
    assert MountPathCategory.STATES_VOLUMES in frontend_usage
    assert frontend_usage[MountPathCategory.HOST] == _get_mocked_disk_usage(
        "1294390525952"
    )
    assert frontend_usage[MountPathCategory.STATES_VOLUMES] == _get_mocked_disk_usage(
        "1GB"
    )

    # emulate data could not be mapped
    disk_usage_monitor.set_disk_usage_for_path(
        {
            "missing_path": _get_mocked_disk_usage("2GB"),
        }
    )
    with pytest.raises(RuntimeError):
        frontend_usage = await _wait_for_usage()
