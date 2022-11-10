# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Iterator
from unittest.mock import AsyncMock, call

import pytest
from pydantic import PositiveFloat
from pytest import FixtureRequest
from pytest_mock.plugin import MockerFixture
from simcore_sdk.node_ports_v2 import Nodeports
from simcore_service_dynamic_sidecar.modules.outputs_manager import OutputsManager


@dataclass
class _MockError:
    error_class: type[BaseException]
    message: str


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
        _MockError(RuntimeError, "emulate_nodeports_raised_error"),
        _MockError(asyncio.CancelledError, ""),
    ]
)
def mock_error(request: FixtureRequest) -> _MockError:
    return request.param


@pytest.fixture
def mock_upload_outputs_raises_error(
    mocker: MockerFixture, mock_error: _MockError
) -> None:
    async def _mock_upload_outputs(*args, **kwargs) -> None:
        raise mock_error.error_class(mock_error.message)

    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs_manager.upload_outputs",
        side_effect=_mock_upload_outputs,
    )


@pytest.fixture(params=[1, 4, 10])
def port_keys(request: FixtureRequest) -> list[str]:
    return [f"port_{i}" for i in range(request.param)]


@pytest.fixture
def outputs_path(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def nodeports() -> Nodeports:
    return AsyncMock()


@pytest.fixture
async def outputs_manager(
    outputs_path: Path, port_keys: list[str], nodeports: Nodeports
) -> AsyncIterator[OutputsManager]:
    outputs_manager = OutputsManager(
        outputs_path=outputs_path, nodeports=nodeports, task_monitor_interval_s=0.1
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
    nodeports: Nodeports,
):
    upload_tasks = [
        outputs_manager.upload_port(port_key=port_key) for port_key in port_keys
    ]

    # wait for tasks to finish uploading
    await asyncio.gather(*upload_tasks)

    assert len(outputs_manager._pending_port_uploads) == 0
    assert mock_upload_outputs.call_count == len(port_keys)

    mock_upload_outputs.assert_has_calls(
        [
            call(outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports)
            for port_key in port_keys
        ],
        any_order=True,
    )


async def test_upload_after_port_change_parallel(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
    nodeports: Nodeports,
    wait_upload_finished: PositiveFloat,
):
    upload_tasks = [
        outputs_manager.upload_after_port_change(port_key=port_key)
        for port_key in port_keys
    ]

    await asyncio.gather(*upload_tasks)
    # wait for tasks to finish uploading
    await asyncio.sleep(wait_upload_finished * len(port_keys))

    assert len(outputs_manager._pending_port_uploads) == 0
    assert mock_upload_outputs.call_count == len(port_keys)

    mock_upload_outputs.assert_has_calls(
        [
            call(outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports)
            for port_key in port_keys
        ],
        any_order=True,
    )


async def test_request_port_upload_case_6(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
    nodeports: Nodeports,
):
    # | # | same_port_as_upload | port_content_changed | upload_exists | action |
    # |---|---------------------|----------------------|---------------|--------|
    # | 6 | true                | false                | true          | N/A    |

    for port_key in port_keys:
        call_count = mock_upload_outputs.call_count
        await outputs_manager.upload_after_port_change(port_key)
        assert mock_upload_outputs.call_count == call_count

        # check nothing was scheduled
        task = asyncio.create_task(outputs_manager.upload_port(port_key))
        assert mock_upload_outputs.call_count == call_count

        # wait for the upload_port task to finish nothing was scheduled
        await task
        assert mock_upload_outputs.call_count == call_count + 1
        mock_upload_outputs.assert_called_with(
            outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports
        )


async def test_request_port_upload_case_8(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
    nodeports: Nodeports,
    wait_upload_finished: PositiveFloat,
):
    # | # | same_port_as_upload | port_content_changed | upload_exists | action            |
    # |---|---------------------|----------------------|---------------|-------------------|
    # | 8 | true                | true                 | true          | cancel & schedule |
    for port_key in port_keys:
        call_count = mock_upload_outputs.call_count

        await outputs_manager.upload_after_port_change(port_key)
        assert mock_upload_outputs.call_count == call_count

        # new upload is scheduled (old one was cancelled)
        await outputs_manager.upload_after_port_change(port_key)
        assert mock_upload_outputs.call_count == call_count

        # wait for upload to finish
        await asyncio.sleep(wait_upload_finished)
        assert mock_upload_outputs.call_count == call_count + 1
        mock_upload_outputs.assert_called_with(
            outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports
        )


async def test_upload_outputs_ok(
    mock_upload_outputs: None,
    outputs_manager: OutputsManager,
    port_keys: list[str],
):
    port_key = port_keys[0]
    result = await outputs_manager.upload_port(port_key)
    assert result is None


async def test_re_raises_error_from_nodeports(
    mock_upload_outputs_raises_error: None,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    mock_error: _MockError,
):
    port_key = port_keys[0]
    with pytest.raises(mock_error.error_class) as exec_info:
        await outputs_manager.upload_port(port_key)
    assert isinstance(exec_info.value, mock_error.error_class)
    assert f"{exec_info.value}" == mock_error.message


# TODO: Important test:
# - start long_running task (mock upload)
# - run another subscriber
# - wait for task to finish and verify result delivery:
#   - verify in case of error
#   - verify in case of cancellation
#   - verify in case of correct result
