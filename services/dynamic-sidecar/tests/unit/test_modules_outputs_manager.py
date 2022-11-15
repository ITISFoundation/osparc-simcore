# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Iterator
from unittest.mock import AsyncMock

import pytest
from pydantic import PositiveFloat
from pytest import FixtureRequest
from pytest_mock.plugin import MockerFixture
from simcore_sdk.node_ports_common.exceptions import S3TransferError
from simcore_service_dynamic_sidecar.modules.outputs_manager import (
    OutputsManager,
    PortKeyTracker,
    UploadPortsFailed,
)

# UTILS


@dataclass
class _MockError:
    error_class: type[BaseException]
    message: str


@dataclass
class ToggleErrorRaising:
    _raise_errors: bool = True

    def stop_raising_errors(self) -> None:
        self._raise_errors = False


# FIXTURES


@pytest.fixture(params=[0.01])
def upload_duration(request: FixtureRequest) -> PositiveFloat:
    return request.param


@pytest.fixture
def wait_upload_finished(upload_duration: PositiveFloat) -> PositiveFloat:
    return upload_duration * 100


@pytest.fixture
def mock_upload_outputs(
    mocker: MockerFixture, upload_duration: PositiveFloat
) -> Iterator[AsyncMock]:
    async def _mock_upload_outputs(*args, **kwargs) -> None:
        await asyncio.sleep(upload_duration)

    yield mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs_manager.upload_outputs",
        side_effect=_mock_upload_outputs,
    )


@pytest.fixture(
    params=[
        _MockError(error_class=RuntimeError, message="mocked_nodeports_raised_error"),
        _MockError(error_class=S3TransferError, message="mocked_s3transfererror"),
    ]
)
def mock_error(request: FixtureRequest) -> _MockError:
    return request.param


@pytest.fixture
def mock_upload_outputs_raises_error(
    mocker: MockerFixture, mock_error: _MockError, upload_duration: PositiveFloat
) -> Iterator[ToggleErrorRaising]:
    error_toggle = ToggleErrorRaising()

    async def _mock_upload_outputs(*args, **kwargs) -> None:
        if error_toggle._raise_errors:
            raise mock_error.error_class(mock_error.message)

        await asyncio.sleep(upload_duration)

    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs_manager.upload_outputs",
        side_effect=_mock_upload_outputs,
    )

    yield error_toggle


@pytest.fixture(params=[1, 4, 10])
def port_keys(request: FixtureRequest) -> list[str]:
    return [f"port_{i}" for i in range(request.param)]


@pytest.fixture
def outputs_path(tmp_path: Path) -> Path:
    return tmp_path


def _assert_ports_uploaded(
    mock_upload_outputs: AsyncMock, port_keys: list[str]
) -> None:
    uploaded_port_keys = []
    assert len(mock_upload_outputs.call_args_list) > 0
    for call_arts in mock_upload_outputs.call_args_list:
        uploaded_port_keys.extend(call_arts.kwargs["port_keys"])

    assert set(uploaded_port_keys) == set(port_keys)


@pytest.fixture
def port_key_tracker() -> PortKeyTracker:
    return PortKeyTracker()


@pytest.fixture
async def port_key_tracker_with_ports(
    port_key_tracker: PortKeyTracker, port_keys: list[str]
) -> PortKeyTracker:
    for port_key in port_keys:
        await port_key_tracker.add_pending(port_key)
    return port_key_tracker


# TESTS


@pytest.fixture
async def outputs_manager(
    outputs_path: Path, port_keys: list[str]
) -> AsyncIterator[OutputsManager]:
    outputs_manager = OutputsManager(
        outputs_path=outputs_path, io_log_redirect_cb=None, task_monitor_interval_s=0.01
    )
    outputs_manager.outputs_port_keys.update(port_keys)
    await outputs_manager.start()
    yield outputs_manager
    await outputs_manager.shutdown()


async def test_upload_port_wait_parallel(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
):
    for port_key in port_keys:
        await outputs_manager.port_key_content_changed(port_key=port_key)

    assert await outputs_manager._port_key_tracker.no_tracked_ports() is False
    await outputs_manager.wait_for_all_uploads_to_finish()
    assert await outputs_manager._port_key_tracker.no_tracked_ports() is True

    _assert_ports_uploaded(mock_upload_outputs, port_keys)


async def test_upload_port_wait_parallel_parallel(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
    wait_upload_finished: PositiveFloat,
):
    upload_tasks = [
        outputs_manager.port_key_content_changed(port_key=port_key)
        for port_key in port_keys
    ]

    await asyncio.gather(*upload_tasks)
    await outputs_manager.wait_for_all_uploads_to_finish()

    _assert_ports_uploaded(mock_upload_outputs, port_keys)


async def test_recovers_after_raising_error(
    mock_upload_outputs_raises_error: ToggleErrorRaising,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    mock_error: _MockError,
):
    # expect to raise error the first time uploading
    for port_key in port_keys:
        await outputs_manager.port_key_content_changed(port_key)
        assert await outputs_manager._port_key_tracker.no_tracked_ports() is False
        await asyncio.sleep(outputs_manager.task_monitor_interval_s * 10)

    with pytest.raises(UploadPortsFailed) as exec_info:
        await outputs_manager.wait_for_all_uploads_to_finish()

    assert set(exec_info.value.failures.keys()) == set(port_keys)

    def _assert_same_exceptions(
        first: list[Exception], second: list[Exception]
    ) -> None:
        assert {x.__class__: f"{x}" for x in first} == {
            x.__class__: f"{x}" for x in second
        }

    _assert_same_exceptions(
        exec_info.value.failures.values(),
        [mock_error.error_class(mock_error.message)] * len(exec_info.value.failures),
    )

    # the second time uploading there is no error to be raised
    mock_upload_outputs_raises_error.stop_raising_errors()
    for port_key in port_keys:
        await outputs_manager.port_key_content_changed(port_key)
        assert await outputs_manager._port_key_tracker.no_tracked_ports() is False
        await asyncio.sleep(outputs_manager.task_monitor_interval_s * 10)

    await outputs_manager.wait_for_all_uploads_to_finish()


async def test_port_key_tracker_add_pending(
    port_key_tracker: PortKeyTracker, port_keys: list[str]
):
    for key in port_keys:
        await port_key_tracker.add_pending(key)
        assert key in port_key_tracker._pending_port_keys
    for key in port_keys:
        assert key not in port_key_tracker._uploading_port_keys


@pytest.mark.parametrize("move_all", [True, False])
async def test_port_key_tracker_are_pending_ports_uploading(
    port_key_tracker_with_ports: PortKeyTracker, port_keys: list[str], move_all: bool
):
    if move_all:
        await port_key_tracker_with_ports.move_all_ports_to_uploading()
    else:
        await port_key_tracker_with_ports.move_port_to_uploading()
    assert await port_key_tracker_with_ports.are_pending_ports_uploading() is False

    for port_key in port_keys:
        await port_key_tracker_with_ports.add_pending(port_key)
    assert await port_key_tracker_with_ports.are_pending_ports_uploading() is True


@pytest.mark.parametrize("move_all", [True, False])
async def test_port_key_tracker_can_schedule_ports_to_upload(
    port_key_tracker_with_ports: PortKeyTracker, move_all: bool
):
    assert await port_key_tracker_with_ports.can_schedule_ports_to_upload() is True
    if move_all:
        await port_key_tracker_with_ports.move_all_ports_to_uploading()
    else:
        await port_key_tracker_with_ports.move_port_to_uploading()
    assert await port_key_tracker_with_ports.can_schedule_ports_to_upload() is False


async def test_port_key_tracker_move_port_to_uploading(
    port_key_tracker_with_ports: PortKeyTracker,
):
    previous_pending = set(port_key_tracker_with_ports._pending_port_keys)
    previous_uploading = set(port_key_tracker_with_ports._uploading_port_keys)
    await port_key_tracker_with_ports.move_port_to_uploading()
    assert len(previous_pending) - 1 == len(
        port_key_tracker_with_ports._pending_port_keys
    )
    assert len(previous_uploading) + 1 == len(
        port_key_tracker_with_ports._uploading_port_keys
    )
    assert len(port_key_tracker_with_ports._uploading_port_keys) == 1
    assert port_key_tracker_with_ports._uploading_port_keys.pop() in previous_pending


async def test_port_key_tracker_move_all_ports_to_uploading(
    port_key_tracker_with_ports: PortKeyTracker,
):
    previous_pending = set(port_key_tracker_with_ports._pending_port_keys)
    assert len(port_key_tracker_with_ports._uploading_port_keys) == 0
    await port_key_tracker_with_ports.move_all_ports_to_uploading()
    assert len(port_key_tracker_with_ports._pending_port_keys) == 0
    assert port_key_tracker_with_ports._uploading_port_keys == previous_pending


async def test_port_key_tracker_move_all_uploading_to_pending(
    port_key_tracker_with_ports: PortKeyTracker,
):
    initial_pending = set(port_key_tracker_with_ports._pending_port_keys)
    initial_uploading = set(port_key_tracker_with_ports._uploading_port_keys)

    assert len(port_key_tracker_with_ports._uploading_port_keys) == 0
    await port_key_tracker_with_ports.move_port_to_uploading()
    await port_key_tracker_with_ports.move_all_uploading_to_pending()
    assert port_key_tracker_with_ports._pending_port_keys == initial_pending
    assert port_key_tracker_with_ports._uploading_port_keys == initial_uploading

    assert len(port_key_tracker_with_ports._uploading_port_keys) == 0
    await port_key_tracker_with_ports.move_all_ports_to_uploading()
    await port_key_tracker_with_ports.move_all_uploading_to_pending()
    assert port_key_tracker_with_ports._pending_port_keys == initial_pending
    assert port_key_tracker_with_ports._uploading_port_keys == initial_uploading


async def test_port_key_tracker_remove_all_uploading(
    port_key_tracker_with_ports: PortKeyTracker,
):
    initial_pending = set(port_key_tracker_with_ports._pending_port_keys)
    initial_uploading = set(port_key_tracker_with_ports._uploading_port_keys)

    assert len(initial_uploading) == 0
    await port_key_tracker_with_ports.move_all_ports_to_uploading()
    assert len(initial_pending) == len(port_key_tracker_with_ports._uploading_port_keys)

    await port_key_tracker_with_ports.remove_all_uploading()
    assert len(port_key_tracker_with_ports._uploading_port_keys) == 0


@pytest.mark.parametrize("move_all", [True, False])
async def test_port_key_tracker_workflow(
    port_key_tracker: PortKeyTracker, port_keys: list[str], move_all: bool
):
    for port_key in port_keys:
        await port_key_tracker.add_pending(port_key)

    assert await port_key_tracker.are_pending_ports_uploading() is False

    assert await port_key_tracker.can_schedule_ports_to_upload() is True
    if move_all:
        await port_key_tracker.move_all_ports_to_uploading()
    else:
        await port_key_tracker.move_port_to_uploading()
    expected_uploading = set(port_key_tracker._uploading_port_keys)
    assert len(expected_uploading) > 0

    assert await port_key_tracker.can_schedule_ports_to_upload() is False

    assert set(await port_key_tracker.get_uploading()) == expected_uploading
