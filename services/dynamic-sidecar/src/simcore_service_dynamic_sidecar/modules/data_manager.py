import logging
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, List

from servicelib.archiving_utils import archive_dir
from servicelib.pools import async_on_threadpool
from simcore_sdk.node_data import data_manager
from simcore_service_dynamic_sidecar.core.settings import (
    DynamicSidecarSettings,
    get_settings,
)

logger = logging.getLogger(__name__)


async def pull_path_if_exists(path: Path) -> None:
    """
    If the path already exist in storage pull it. Otherwise it is assumed
    this is the first time the service starts.

    In each and every other case an error is raised and logged
    """
    settings: DynamicSidecarSettings = get_settings()

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


@asynccontextmanager
async def _isolated_temp_zip_path(path_to_compress: Path) -> AsyncIterator[Path]:
    base_dir = Path(tempfile.mkdtemp())
    zip_temp_name = base_dir / f"{path_to_compress.name}.zip"
    try:
        yield zip_temp_name
    finally:
        await async_on_threadpool(lambda: shutil.rmtree(base_dir, ignore_errors=True))


async def upload_path_if_exists(path: Path, state_exclude: List[Path]) -> None:
    """
    Zips the path in a temporary directory and uploads to storage
    """
    settings: DynamicSidecarSettings = get_settings()
    # pylint: disable=unnecessary-comprehension
    logger.info("Files in %s: %s", path, [x for x in path.rglob("*")])

    async with _isolated_temp_zip_path(path) as archive_path:
        await archive_dir(
            dir_to_compress=path,
            destination=archive_path,
            compress=False,
            store_relative_path=True,
            exclude_paths=state_exclude,
        )
        await data_manager.push(
            user_id=settings.DY_SIDECAR_USER_ID,
            project_id=str(settings.DY_SIDECAR_PROJECT_ID),
            node_uuid=str(settings.DY_SIDECAR_NODE_ID),
            file_or_folder=path,
        )
    logger.info("Finished upload of %s", path)
