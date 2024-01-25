# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from models_library.projects_nodes_io import NodeID
from models_library.users import GroupID
from psutil._common import sdiskusage
from pydantic import ByteSize
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage import (
    DiskUsageMonitor,
    get_usage,
)


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
        primary_group_id: GroupID,
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
    return ByteSize.validate(byte_size_as_str)


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
    publish_disk_usage_spy: Mock,
    faker: Faker,
) -> None:
    disk_usage_monitor = DiskUsageMonitor(
        app=AsyncMock(),
        primary_group_id=42,
        node_id=faker.uuid4(),
        interval=timedelta(seconds=5),
        monitored_paths=[Path("/"), Path("/tmp")],  # noqa: S108
    )

    assert len(publish_disk_usage_spy.call_args_list) == 0

    for i in range(1, 3):
        mock_disk_usage(
            {
                "/": _get_byte_size(f"{i}kb"),
                "/tmp": _get_byte_size(f"{i*2}kb"),  # noqa: S108
            }
        )

        await _assert_monitor_triggers(
            disk_usage_monitor, publish_disk_usage_spy, expected_events=1
        )

        assert _get_entry(publish_disk_usage_spy, index=0) == {
            Path("/"): _get_mocked_disk_usage(f"{i}kb"),
            Path("/tmp"): _get_mocked_disk_usage(f"{i*2}kb"),  # noqa: S108
        }

        # reset mock to test again
        publish_disk_usage_spy.reset_mock()


def _random_tmp_file(tmp_path: Path, faker: Faker) -> None:
    some_path: Path = tmp_path / faker.uuid4()
    some_path.write_text("some text here")


async def test_get_usage(tmp_path: Path, faker: Faker):
    usage_before = await get_usage(Path("/"))
    _random_tmp_file(tmp_path, faker)
    usage_after = await get_usage(Path("/"))

    assert usage_after.free < usage_before.free
