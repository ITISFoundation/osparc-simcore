# pylint: disable=unused-argument

from pathlib import Path

import pytest
from async_asgi_testclient import TestClient
from fastapi import status
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore


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
    test_client: TestClient,
    volume_category: VolumeCategory,
    initial_expected_status: VolumeStatus,
):
    shared_store: SharedStore = test_client.application.state.shared_store

    # check that initial status is as expected
    assert shared_store.volume_states[volume_category] == VolumeState(
        status=initial_expected_status
    )

    response = await test_client.put(
        f"/{API_VTAG}/volumes/{volume_category}",
        json={"status": VolumeStatus.CONTENT_WAS_SAVED},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

    # check that
    assert shared_store.volume_states[volume_category] == VolumeState(
        status=VolumeStatus.CONTENT_WAS_SAVED
    )


@pytest.mark.parametrize("invalid_volume_category", ["outputs", "outputS"])
async def test_volumes_state_saved_error(
    ensure_shared_store_dir: Path,
    test_client: TestClient,
    invalid_volume_category: VolumeCategory,
):
    response = await test_client.put(
        f"/{API_VTAG}/volumes/{invalid_volume_category}",
        json={"status": VolumeStatus.CONTENT_WAS_SAVED},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    json_response = response.json()
    assert invalid_volume_category not in json_response["detail"][0]["ctx"]["expected"]
