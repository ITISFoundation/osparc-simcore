# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import container_extensions
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.outputs._watcher import OutputsWatcher
from simcore_service_dynamic_sidecar.services.inputs import InputsState

pytest_simcore_core_services_selection = [
    "rabbit",
]


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
