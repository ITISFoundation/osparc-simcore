# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from pathlib import Path

import pytest
from fastapi import FastAPI
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq._errors import RPCServerError
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import volumes
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.mark.parametrize(
    "volume_category, initial_expected_status",
    [
        (VolumeCategory.STATES, VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED),
        (VolumeCategory.OUTPUTS, VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED),
        (VolumeCategory.INPUTS, VolumeStatus.CONTENT_NO_SAVE_REQUIRED),
        (VolumeCategory.SHARED_STORE, VolumeStatus.CONTENT_NO_SAVE_REQUIRED),
    ],
)
async def test_volumes_state_saved_ok(
    ensure_shared_store_dir: Path,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    volume_category: VolumeCategory,
    initial_expected_status: VolumeStatus,
):
    shared_store: SharedStore = app.state.shared_store
    settings: ApplicationSettings = app.state.settings

    # check that initial status is as expected
    assert shared_store.volume_states[volume_category] == VolumeState(
        status=initial_expected_status
    )

    await volumes.save_volume_state(
        rpc_client,
        node_id=settings.DY_SIDECAR_NODE_ID,
        status=VolumeStatus.CONTENT_WAS_SAVED,
        category=volume_category,
    )

    # check that
    assert shared_store.volume_states[volume_category] == VolumeState(
        status=VolumeStatus.CONTENT_WAS_SAVED
    )


@pytest.mark.parametrize("invalid_volume_category", ["outputs", "outputS"])
async def test_volumes_state_saved_error(
    ensure_shared_store_dir: Path,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    invalid_volume_category: VolumeCategory,
):

    settings: ApplicationSettings = app.state.settings

    with pytest.raises(RPCServerError, match="ValidationError"):
        await volumes.save_volume_state(
            rpc_client,
            node_id=settings.DY_SIDECAR_NODE_ID,
            status=VolumeStatus.CONTENT_WAS_SAVED,
            category=invalid_volume_category,
        )
