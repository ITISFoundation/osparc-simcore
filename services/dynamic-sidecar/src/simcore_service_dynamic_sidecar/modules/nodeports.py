import json
import logging
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, List, Optional, cast

from servicelib.archiving_utils import archive_dir
from servicelib.async_utils import run_sequentially_in_context
from servicelib.utils import logged_gather
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_v2 import Nodeports, Port
from simcore_service_dynamic_sidecar.core.settings import (
    NonFastAPIDynamicSidecarSettings,
    get_non_fastpi_settings,
)

_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

logger = logging.getLogger(__name__)


async def _set_data_to_port(port: Port, value: Optional[Any]) -> int:
    logger.info("transfer started for %s", port.key)

    start_time = time.perf_counter()
    await port.set(value)
    elapsed_time = time.perf_counter() - start_time

    logger.info("transfer completed in %ss", elapsed_time)

    if isinstance(value, Path):
        size_bytes = value.stat().st_size
        logger.info(
            "%s: data size: %sMB, transfer rate %sMB/s",
            value.name,
            size_bytes / 1024 / 1024,
            size_bytes / 1024 / 1024 / elapsed_time,
        )
        return size_bytes
    return sys.getsizeof(value)


@run_sequentially_in_context()
async def upload_outputs(port_keys: List[str]) -> None:
    """calls to this function will get queued and invoked in sequence"""
    # pylint: disable=too-many-branches
    logger.info("uploading data to simcore...")
    start_time = time.perf_counter()

    settings: NonFastAPIDynamicSidecarSettings = get_non_fastpi_settings()
    PORTS: Nodeports = await node_ports_v2.ports(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=str(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=str(settings.DY_SIDECAR_NODE_ID),
    )

    # let's gather the tasks
    temp_files: List[Path] = []
    upload_tasks = []

    for port in (await PORTS.outputs).values():
        logger.info("Checking port %s", port.key)
        if port_keys and port.key not in port_keys:
            continue
        logger.debug(
            "uploading data to port '%s' with value '%s'...", port.key, port.value
        )
        if _FILE_TYPE_PREFIX in port.property_type:
            src_folder = settings.DY_SIDECAR_PATH_OUTPUTS / port.key
            files_and_folders_list = list(src_folder.rglob("*"))

            if not files_and_folders_list:
                upload_tasks.append(_set_data_to_port(port, None))
                continue

            if len(files_and_folders_list) == 1 and files_and_folders_list[0].is_file():
                # special case, direct upload
                upload_tasks.append(_set_data_to_port(port, files_and_folders_list[0]))
                continue

            # generic case let's create an archive
            # only the filtered out files will be zipped
            tmp_file = Path(tempfile.mkdtemp()) / f"{src_folder.stem}.zip"
            temp_files.append(tmp_file)

            zip_was_created = await archive_dir(
                dir_to_compress=src_folder,
                destination=tmp_file,
                compress=False,
                store_relative_path=True,
            )
            if zip_was_created:
                upload_tasks.append(_set_data_to_port(port, tmp_file))
            else:
                logger.error("Could not create zip archive, nothing will be uploaded")
        else:
            data_file = settings.DY_SIDECAR_PATH_OUTPUTS / _KEY_VALUE_FILE_NAME
            if data_file.exists():
                data = json.loads(data_file.read_text())
                if port.key in data and data[port.key] is not None:
                    upload_tasks.append(_set_data_to_port(port, data[port.key]))

    total_bytes: int = 0
    if upload_tasks:
        try:
            results = cast(List[int], await logged_gather(*upload_tasks))
            total_bytes = sum(results)
        finally:
            # clean up possible compressed files
            for file_path in temp_files:
                # TODO: run this on threadpool
                shutil.rmtree(file_path.parent, ignore_errors=True)

    elapsed_time = time.perf_counter() - start_time
    logger.info("Uploaded %s bytes in %s seconds", total_bytes, elapsed_time)


async def dispatch_update_for_directory(directory_path: Path) -> None:
    logger.info("Uploading data for directory %s", directory_path)

    settings: NonFastAPIDynamicSidecarSettings = get_non_fastpi_settings()
    if directory_path == settings.DY_SIDECAR_PATH_OUTPUTS:
        await upload_outputs([])


__all__ = ["dispatch_update_for_directory"]
