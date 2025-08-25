# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import asyncio
from typing import Final
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from models_library.services import ServiceOutput
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import container_extensions
from simcore_service_dynamic_sidecar.core.application import AppState
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.inputs import InputsState
from simcore_service_dynamic_sidecar.modules.outputs._watcher import OutputsWatcher

pytest_simcore_core_services_selection = [
    "rabbit",
]

_WAIT_FOR_OUTPUTS_WATCHER: Final[float] = 0.1


def _assert_inputs_pulling(app: FastAPI, is_enabled: bool) -> None:
    inputs_state: InputsState = app.state.inputs_state
    assert inputs_state.inputs_pulling_enabled is is_enabled


def _assert_outputs_event_propagation(
    spy_output_watcher: dict[str, AsyncMock], is_enabled: bool
) -> None:
    assert spy_output_watcher["disable_event_propagation"].call_count == (
        1 if not is_enabled else 0
    )
    assert spy_output_watcher["enable_event_propagation"].call_count == (
        1 if is_enabled else 0
    )


@pytest.fixture
def spy_output_watcher(mocker: MockerFixture) -> dict[str, AsyncMock]:
    return {
        "disable_event_propagation": mocker.spy(
            OutputsWatcher, "disable_event_propagation"
        ),
        "enable_event_propagation": mocker.spy(
            OutputsWatcher, "enable_event_propagation"
        ),
    }


@pytest.mark.parametrize("enabled", [True, False])
async def test_toggle_ports_io(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    enabled: bool,
    spy_output_watcher: dict[str, AsyncMock],
):
    settings: ApplicationSettings = app.state.settings

    result = await container_extensions.toggle_ports_io(
        rpc_client,
        node_id=settings.DY_SIDECAR_NODE_ID,
        enable_outputs=enabled,
        enable_inputs=enabled,
    )
    assert result is None

    _assert_inputs_pulling(app, enabled)
    _assert_outputs_event_propagation(spy_output_watcher, enabled)


@pytest.fixture
def mock_outputs_labels() -> dict[str, ServiceOutput]:
    return {
        "output_port_1": TypeAdapter(ServiceOutput).validate_python(
            ServiceOutput.model_json_schema()["examples"][3]
        ),
        "output_port_2": TypeAdapter(ServiceOutput).validate_python(
            ServiceOutput.model_json_schema()["examples"][3]
        ),
    }


@pytest.fixture
def mock_event_filter_enqueue(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> AsyncMock:
    mock = AsyncMock(return_value=None)
    outputs_watcher: OutputsWatcher = app.state.outputs_watcher
    monkeypatch.setattr(outputs_watcher._event_filter, "enqueue", mock)  # noqa: SLF001
    return mock


async def test_container_create_outputs_dirs(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_outputs_labels: dict[str, ServiceOutput],
    mock_event_filter_enqueue: AsyncMock,
):
    app_state = AppState(app)

    # by default outputs-watcher it is disabled
    result = await container_extensions.toggle_ports_io(
        rpc_client,
        node_id=app_state.settings.DY_SIDECAR_NODE_ID,
        enable_outputs=True,
        enable_inputs=True,
    )
    assert result is None
    await asyncio.sleep(_WAIT_FOR_OUTPUTS_WATCHER)

    assert mock_event_filter_enqueue.call_count == 0

    result = await container_extensions.create_output_dirs(
        rpc_client,
        node_id=app_state.settings.DY_SIDECAR_NODE_ID,
        outputs_labels=mock_outputs_labels,
    )

    for dir_name in mock_outputs_labels:
        assert (app_state.mounted_volumes.disk_outputs_path / dir_name).is_dir()

    await asyncio.sleep(_WAIT_FOR_OUTPUTS_WATCHER)
    EXPECT_EVENTS_WHEN_CREATING_OUTPUT_PORT_KEY_DIRS = 0
    assert (
        mock_event_filter_enqueue.call_count
        == EXPECT_EVENTS_WHEN_CREATING_OUTPUT_PORT_KEY_DIRS
    )
