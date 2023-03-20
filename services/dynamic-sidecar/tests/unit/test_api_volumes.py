from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from models_library.volumes import VolumeCategory
from servicelib.volumes_utils import AGENT_FILE_NAME, VolumeState, load_volume_state
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes


@pytest.mark.parametrize(
    "volume_category", [VolumeCategory.STATES, VolumeCategory.OUTPUTS]
)
async def test_volumes_state_saved_ok(test_client: TestClient, volume_category: str):
    mounted_volumes: MountedVolumes = test_client.application.state.mounted_volumes

    volumes_path_map: dict[str, list[Path]] = {
        "states": list(mounted_volumes.disk_state_paths()),
        "outputs": [mounted_volumes.disk_outputs_path],
    }

    for path in volumes_path_map[volume_category]:
        assert await load_volume_state(path / AGENT_FILE_NAME) == VolumeState(
            requires_saving=True, was_saved=False
        )

    response = await test_client.patch(
        f"/{API_VTAG}/volumes/{volume_category}",
        json={"requires_saving": True, "was_saved": True},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

    for path in volumes_path_map[volume_category]:
        assert await load_volume_state(path / AGENT_FILE_NAME) == VolumeState(
            requires_saving=True, was_saved=True
        )


@pytest.mark.parametrize("invalid_volume_id", ["OUTPUTS", "outputS"])
async def test_volumes_state_saved_error(
    test_client: TestClient, invalid_volume_id: str
):
    response = await test_client.patch(
        f"/{API_VTAG}/volumes/{invalid_volume_id}",
        json={"requires_saving": True, "was_saved": True},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    json_response = response.json()
    assert invalid_volume_id not in json_response["detail"][0]["ctx"]["enum_values"]
