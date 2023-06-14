import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import aiofiles
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus
from pydantic import parse_obj_as
from servicelib.sidecar_volumes import (
    REGULAR_SOURCE_PORTION_LEN,
    STORE_FILE_NAME,
    VolumeUtils,
)

from ...core.settings import ApplicationSettings
from ..docker import delete_volume, docker_client, is_volume_present, is_volume_used
from ._s3 import store_to_s3
from .models import VolumeDict

SHARED_STORE_PATH = Path("/dy-volumes/shared-store")

_logger = logging.getLogger(__name__)


@dataclass
class SidecarVolumes:
    store_volume: VolumeDict
    remaining_volumes: list[VolumeDict]

    @classmethod
    def from_volumes(cls, volumes: Iterable[VolumeDict]) -> "SidecarVolumes":
        volumes_common_part: set[str] = {
            v["Name"][:REGULAR_SOURCE_PORTION_LEN] for v in volumes
        }
        if len(volumes_common_part) != 1:
            raise ValueError(f"Volumes do not share the same common part: {volumes=}")

        params = {"store_volume": None, "remaining_volumes": []}

        for volume in volumes:
            reverted_possible_volume_name = volume["Name"][78:]
            possible_volume_name = reverted_possible_volume_name[::-1]
            if possible_volume_name == VolumeUtils.get_name(SHARED_STORE_PATH):
                params["store_volume"] = volume
            else:
                params["remaining_volumes"].append(volume)

        if params["store_volume"] is None:
            raise ValueError(f"No 'store_volume' detected in {volumes=}")

        return cls(**params)

    def __str__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"store_volume={self.store_volume['Name']}, "
            f"remaining_volumes={[v['Name'] for v in self.remaining_volumes]}>"
        )


def get_sidecar_volumes_list(volumes: list[VolumeDict]) -> list[SidecarVolumes]:
    """groups volumes by their shared common part"""
    # example of regular source portion (always has the same length)
    # dyv_f96e0350-407b-4d68-9fba-a95d4d1e60fd_78f06db4-5feb-4ea3-ad1b-176310ac71a7_

    # NOTE: ideally  the type below would be dict[str, set[VolumeDict]] but
    # unfortunately set's can't contain dicts since they are not hashable
    detected_volumes: dict[str, dict[str, VolumeDict]] = {}
    for volume in volumes:
        volume_name = volume["Name"]
        shared_volume_part = volume_name[:REGULAR_SOURCE_PORTION_LEN]

        if shared_volume_part not in detected_volumes:
            detected_volumes[shared_volume_part] = {}
        detected_volumes[shared_volume_part][volume_name] = volume

    return [SidecarVolumes.from_volumes(x.values()) for x in detected_volumes.values()]


async def _get_volumes_status(
    store_volume: VolumeDict,
) -> dict[str, VolumeStatus]:
    store_file_path = Path(store_volume["Mountpoint"]) / STORE_FILE_NAME

    async with aiofiles.open(store_file_path) as data_file:
        file_content = await data_file.read()

    volume_states_dict = json.loads(file_content)["volume_states"]
    stored_volume: dict[VolumeCategory, VolumeState] = parse_obj_as(
        dict[VolumeCategory, VolumeState], volume_states_dict
    )

    volumes_status: dict[str, VolumeStatus] = {}
    for volume_state in stored_volume.values():
        for volume_name in volume_state.volume_names:
            volumes_status[volume_name] = volume_state.status
    return volumes_status


async def backup_and_remove_sidecar_volumes(
    settings: ApplicationSettings, sidecar_volumes: SidecarVolumes
) -> None:
    """Backs up and removes sidecar volumes"""
    # NOTE: this method is guaranteed to run sequentially

    async with docker_client() as client:
        if not await is_volume_present(client, sidecar_volumes.store_volume["Name"]):
            _logger.info("No data volume found %s", sidecar_volumes.store_volume)
            return
        if await is_volume_used(client, sidecar_volumes.store_volume["Name"]):
            _logger.info("The following volumes are being used %s", sidecar_volumes)
            return

        volumes_status: dict[str, VolumeStatus] = await _get_volumes_status(
            sidecar_volumes.store_volume
        )

        volumes_to_names_map: dict[str, VolumeDict] = {
            v["Name"]: v for v in sidecar_volumes.remaining_volumes
        }

        # check if all the volumes_to_remove have a listing in the volumes_with_states
        volumes_to_remove: set[str] = {
            v["Name"] for v in sidecar_volumes.remaining_volumes
        }
        volumes_with_states = set(volumes_status.keys())
        if not volumes_to_remove.issubset(volumes_with_states):
            raise RuntimeError(
                f"Not all volumes which must be backed up have a state. "
                f"Expected to find an entry for each element in {volumes_to_remove=} "
                f"inside {volumes_with_states=}."
            )

        errors_during_save: bool = False
        for volume_to_remove in volumes_to_remove:
            if not await is_volume_present(client, volume_to_remove):
                _logger.info("Volume %s not found. Skipping", volume_to_remove)
                continue
            if await is_volume_used(client, volume_to_remove):
                _logger.warning(
                    "Volume %s was not saved because in use and will remain on the system.",
                    volume_to_remove,
                )
                continue

            # check if volume requires backup and remove it
            volume_status: VolumeStatus = volumes_status[volume_to_remove]
            if volume_status == VolumeStatus.CONTENT_NEEDS_TO_BE_SAVED:
                volume: VolumeDict = volumes_to_names_map[volume_to_remove]
                _logger.info("Backing up volume %s", volume_to_remove)
                try:
                    await store_to_s3(
                        volume_name=volume_to_remove,
                        dyv_volume=volume,
                        s3_endpoint=settings.AGENT_VOLUMES_CLEANUP_S3_ENDPOINT,
                        s3_access_key=settings.AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY,
                        s3_secret_key=settings.AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY,
                        s3_bucket=settings.AGENT_VOLUMES_CLEANUP_S3_BUCKET,
                        s3_region=settings.AGENT_VOLUMES_CLEANUP_S3_REGION,
                        s3_provider=settings.AGENT_VOLUMES_CLEANUP_S3_PROVIDER,
                        s3_retries=settings.AGENT_VOLUMES_CLEANUP_RETRIES,
                        s3_parallelism=settings.AGENT_VOLUMES_CLEANUP_PARALLELISM,
                        exclude_files=settings.AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES,
                    )
                except Exception as e:  # pylint:disable=broad-except
                    errors_during_save = True
                    _logger.error("%s", e)
                    continue

            await delete_volume(client, volume_to_remove)

        # finally remove the data volume
        if not errors_during_save:
            await delete_volume(client, sidecar_volumes.store_volume["Name"])
        else:
            _logger.warning(
                "State volume %s was not removed since there were errors, check above!",
                sidecar_volumes.store_volume["Name"],
            )
