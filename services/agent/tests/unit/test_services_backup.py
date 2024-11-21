# pylint: disable=redefined-outer-name

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final
from uuid import uuid4

import aioboto3
import pytest
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import RunID
from pydantic import NonNegativeInt
from simcore_service_agent.core.settings import ApplicationSettings
from simcore_service_agent.services.backup import backup_volume
from simcore_service_agent.services.docker_utils import get_volume_details
from simcore_service_agent.services.volumes_manager import VolumesManager
from utils import VOLUMES_TO_CREATE

pytest_simcore_core_services_selection = [
    "rabbit",
]

_FILES_TO_CREATE_IN_VOLUME: Final[NonNegativeInt] = 10


@pytest.fixture
def volume_content(tmpdir: Path) -> Path:
    path = Path(tmpdir) / "to_copy"
    path.mkdir(parents=True, exist_ok=True)

    for i in range(_FILES_TO_CREATE_IN_VOLUME):
        (path / f"f{i}").write_text(f"some text for file {i}\n" * (i + 1))

    return path


@pytest.fixture
def downlaoded_from_s3(tmpdir: Path) -> Path:
    path = Path(tmpdir) / "downloaded_from_s3"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def test_backup_volume(
    volume_content: Path,
    project_id: ProjectID,
    swarm_stack_name: str,
    run_id: RunID,
    downlaoded_from_s3: Path,
    create_dynamic_sidecar_volumes: Callable[[NodeID, bool], Awaitable[set[str]]],
    initialized_app: FastAPI,
):
    node_id = uuid4()
    volumes: set[str] = await create_dynamic_sidecar_volumes(
        node_id, True  # noqa: FBT003
    )

    for volume in volumes:
        volume_details = await get_volume_details(
            VolumesManager.get_from_app_state(initialized_app).docker,
            volume_name=volume,
        )
        # root permissions are required to access the /var/docker data
        # overwriting with a mocked path for this test
        volume_details.mountpoint = volume_content
        await backup_volume(initialized_app, volume_details, volume)

    settings: ApplicationSettings = initialized_app.state.settings

    session = aioboto3.Session(
        aws_access_key_id=settings.AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY,
        aws_secret_access_key=settings.AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY,
    )

    expected_files = _FILES_TO_CREATE_IN_VOLUME * len(VOLUMES_TO_CREATE)

    async with session.client("s3", endpoint_url=f"{settings.AGENT_VOLUMES_CLEANUP_S3_ENDPOINT}") as s3_client:  # type: ignore
        list_response = await s3_client.list_objects_v2(
            Bucket=settings.AGENT_VOLUMES_CLEANUP_S3_BUCKET,
            Prefix=f"{swarm_stack_name}/{project_id}/{node_id}/{run_id}",
        )
        synced_keys: list[str] = [o["Key"] for o in list_response["Contents"]]

        assert len(synced_keys) == expected_files

        async def _download_file(key: str) -> None:
            key_path = Path(key)
            (downlaoded_from_s3 / key_path.parent.name).mkdir(
                parents=True, exist_ok=True
            )
            await s3_client.download_file(
                settings.AGENT_VOLUMES_CLEANUP_S3_BUCKET,
                key,
                downlaoded_from_s3 / key_path.parent.name / key_path.name,
            )

        await asyncio.gather(*[_download_file(key) for key in synced_keys])

        assert (
            len([x for x in downlaoded_from_s3.rglob("*") if x.is_file()])
            == expected_files
        )
