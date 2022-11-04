# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from pathlib import Path
from typing import AsyncIterator, Iterator
from unittest.mock import AsyncMock

import pytest
from pydantic import PositiveFloat
from pytest import FixtureRequest
from pytest_mock.plugin import MockerFixture
from simcore_sdk.node_ports_v2 import Nodeports
from simcore_service_dynamic_sidecar.modules.outputs_manager import OutputsManager


@pytest.fixture(params=[0.01, 0.1])
def upload_duration(request: FixtureRequest) -> PositiveFloat:
    return request.param


@pytest.fixture
def event_generation_rate(upload_duration: PositiveFloat) -> PositiveFloat:
    return upload_duration / 10


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


@pytest.fixture(params=[1, 2, 3, 4, 10])
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
    outputs_manager = OutputsManager(outputs_path=outputs_path, nodeports=nodeports)
    outputs_manager.outputs_port_keys.update(port_keys)
    yield outputs_manager
    await outputs_manager.shutdown()


async def test_upload_port_sequential_calls(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    upload_duration: PositiveFloat,
    outputs_path: Path,
    nodeports: Nodeports,
):
    assert mock_upload_outputs.call_count == 0
    for port_key in port_keys:

        # `upload_port` calls upload_outputs
        call_counter = mock_upload_outputs.call_count
        await outputs_manager.upload_port(port_key=port_key)
        mock_upload_outputs.assert_called_with(
            outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports
        )
        assert mock_upload_outputs.call_count == call_counter + 1

        # `upload_port` does not call upload_outputs
        # since an upload is already ongoing and there are no further changes
        call_counter = mock_upload_outputs.call_count
        assert port_key in outputs_manager._current_uploads
        first_task_id = outputs_manager._current_uploads[port_key]
        await outputs_manager.upload_port(port_key=port_key)
        assert mock_upload_outputs.call_count == call_counter
        second_task_id = outputs_manager._current_uploads[port_key]
        assert first_task_id == second_task_id

        # after upload is finished
        # `upload_port` calls upload_outputs again
        await asyncio.sleep(upload_duration * 2)
        assert port_key not in outputs_manager._current_uploads
        call_counter = mock_upload_outputs.call_count
        await outputs_manager.upload_port(port_key=port_key)
        assert mock_upload_outputs.call_count == call_counter + 1
        third_task_id = outputs_manager._current_uploads[port_key]
        assert second_task_id != third_task_id


async def test_upload_after_port_change_sequential_calls(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    upload_duration: PositiveFloat,
    outputs_path: Path,
    nodeports: Nodeports,
):
    assert mock_upload_outputs.call_count == 0
    for port_key in port_keys:

        # `upload_after_port_change` calls upload_outputs
        call_counter = mock_upload_outputs.call_count
        await outputs_manager.upload_after_port_change(port_key=port_key)
        mock_upload_outputs.assert_called_with(
            outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports
        )
        assert mock_upload_outputs.call_count == call_counter + 1

        # `upload_after_port_change` cancels task and
        # once again calls upload_outputs
        assert port_key in outputs_manager._current_uploads
        first_task_id = outputs_manager._current_uploads[port_key]
        call_counter = mock_upload_outputs.call_count
        await outputs_manager.upload_after_port_change(port_key=port_key)
        assert mock_upload_outputs.call_count == call_counter + 1
        assert port_key in outputs_manager._current_uploads
        second_task_id = outputs_manager._current_uploads[port_key]
        assert first_task_id != second_task_id

        # after upload is finished
        # `upload_after_port_change` calls upload_outputs again
        await asyncio.sleep(upload_duration * 2)
        assert port_key not in outputs_manager._current_uploads
        call_counter = mock_upload_outputs.call_count
        await outputs_manager.upload_after_port_change(port_key=port_key)
        assert mock_upload_outputs.call_count == call_counter + 1
        third_task_id = outputs_manager._current_uploads[port_key]
        assert second_task_id != third_task_id


async def test_upload_after_port_change_cancels_upload_port(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
    nodeports: Nodeports,
):
    assert mock_upload_outputs.call_count == 0
    for port_key in port_keys:

        # `upload_port` calls upload_outputs
        call_counter = mock_upload_outputs.call_count
        await outputs_manager.upload_port(port_key=port_key)
        mock_upload_outputs.assert_called_with(
            outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports
        )
        assert mock_upload_outputs.call_count == call_counter + 1

        # `upload_after_port_change` cancels task and
        # once again calls upload_outputs
        assert port_key in outputs_manager._current_uploads
        first_task_id = outputs_manager._current_uploads[port_key]
        call_counter = mock_upload_outputs.call_count
        await outputs_manager.upload_after_port_change(port_key=port_key)
        assert mock_upload_outputs.call_count == call_counter + 1
        assert port_key in outputs_manager._current_uploads
        second_task_id = outputs_manager._current_uploads[port_key]
        assert first_task_id != second_task_id


async def test_upload_port_does_not_cancel_upload_after_port_change(
    mock_upload_outputs: AsyncMock,
    outputs_manager: OutputsManager,
    port_keys: list[str],
    outputs_path: Path,
    nodeports: Nodeports,
):
    assert mock_upload_outputs.call_count == 0
    for port_key in port_keys:

        # `upload_after_port_change` calls upload_outputs
        call_counter = mock_upload_outputs.call_count
        await outputs_manager.upload_after_port_change(port_key=port_key)
        mock_upload_outputs.assert_called_with(
            outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports
        )
        assert mock_upload_outputs.call_count == call_counter + 1

        # `upload_port` does not call upload_outputs
        # since an upload is already ongoing and there are no further changes
        call_counter = mock_upload_outputs.call_count
        assert port_key in outputs_manager._current_uploads
        first_task_id = outputs_manager._current_uploads[port_key]
        await outputs_manager.upload_port(port_key=port_key)
        assert mock_upload_outputs.call_count == call_counter
        second_task_id = outputs_manager._current_uploads[port_key]
        assert first_task_id == second_task_id
