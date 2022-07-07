import logging
from pathlib import Path

from simcore_sdk.node_data import data_manager
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings

logger = logging.getLogger(__name__)


async def pull_path_if_exists(path: Path, settings: DynamicSidecarSettings) -> None:
    """
    If the path already exist in storage pull it. Otherwise it is assumed
    this is the first time the service starts.

    In each and every other case an error is raised and logged
    """

    if not await data_manager.is_file_present_in_storage(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=str(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=str(settings.DY_SIDECAR_NODE_ID),
        file_path=path,
    ):
        logger.info(
            "File '%s' is not present in storage service, will skip.", str(path)
        )
        return

    await data_manager.pull(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=str(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=str(settings.DY_SIDECAR_NODE_ID),
        file_or_folder=path,
    )
    logger.info("Finished pulling and extracting %s", str(path))


async def upload_path_if_exists(
    path: Path, state_exclude: list[str], settings: DynamicSidecarSettings
) -> None:
    """
    Zips the path in a temporary directory and uploads to storage
    """
    await data_manager.push(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=str(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=str(settings.DY_SIDECAR_NODE_ID),
        file_or_folder=path,
        r_clone_settings=settings.rclone_settings_for_nodeports,
        archive_exclude_patterns=state_exclude,
    )
    logger.info("Finished upload of %s", path)
