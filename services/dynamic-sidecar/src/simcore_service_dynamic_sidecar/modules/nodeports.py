import json
import logging
import shutil
import sys
import tempfile
import time
import zipfile
from collections import deque
from pathlib import Path
from typing import Coroutine, Deque, Dict, List, Optional, Set, Tuple, cast

from pydantic import ByteSize
from servicelib.archiving_utils import PrunableFolder, archive_dir, unarchive_dir
from servicelib.async_utils import run_sequentially_in_context
from servicelib.file_utils import remove_directory
from servicelib.pools import async_on_threadpool
from servicelib.utils import logged_gather
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_v2 import Nodeports, Port
from simcore_sdk.node_ports_v2.links import ItemConcreteValue
from simcore_service_dynamic_sidecar.core.settings import (
    DynamicSidecarSettings,
    get_settings,
)

_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

logger = logging.getLogger(__name__)

# OUTPUTS section


def _get_size_of_value(value: ItemConcreteValue) -> int:
    if isinstance(value, Path):
        size_bytes = value.stat().st_size
        return size_bytes
    return sys.getsizeof(value)


@run_sequentially_in_context()
async def upload_outputs(outputs_path: Path, port_keys: List[str]) -> None:
    """calls to this function will get queued and invoked in sequence"""
    # pylint: disable=too-many-branches
    logger.info("uploading data to simcore...")
    start_time = time.perf_counter()

    settings: DynamicSidecarSettings = get_settings()
    PORTS: Nodeports = await node_ports_v2.ports(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=str(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=str(settings.DY_SIDECAR_NODE_ID),
    )

    # let's gather the tasks
    temp_files: List[Path] = []
    ports_values: Dict[str, ItemConcreteValue] = {}
    archiving_tasks: Deque[Coroutine[None, None, None]] = deque()

    for port in (await PORTS.outputs).values():
        logger.info("Checking port %s", port.key)
        if port_keys and port.key not in port_keys:
            continue
        logger.debug(
            "uploading data to port '%s' with value '%s'...", port.key, port.value
        )
        if _FILE_TYPE_PREFIX in port.property_type:
            src_folder = outputs_path / port.key
            files_and_folders_list = list(src_folder.rglob("*"))

            if not files_and_folders_list:
                ports_values[port.key] = None
                continue

            if len(files_and_folders_list) == 1 and files_and_folders_list[0].is_file():
                # special case, direct upload
                ports_values[port.key] = files_and_folders_list[0]
                continue

            # generic case let's create an archive
            # only the filtered out files will be zipped
            tmp_file = Path(tempfile.mkdtemp()) / f"{src_folder.stem}.zip"
            temp_files.append(tmp_file)

            # when having multiple directories it is important to
            # run the compression in parallel to guarantee better performance
            archiving_tasks.append(
                archive_dir(
                    dir_to_compress=src_folder,
                    destination=tmp_file,
                    compress=False,
                    store_relative_path=True,
                )
            )
            ports_values[port.key] = tmp_file
        else:
            data_file = outputs_path / _KEY_VALUE_FILE_NAME
            if data_file.exists():
                data = json.loads(data_file.read_text())
                if port.key in data and data[port.key] is not None:
                    ports_values[port.key] = data[port.key]
                else:
                    logger.debug("Port %s not found in %s", port.key, data)
            else:
                logger.debug("No file %s to fetch port values from", data_file)

    try:
        if archiving_tasks:
            await logged_gather(*archiving_tasks)
        await PORTS.set_multiple(ports_values)

        elapsed_time = time.perf_counter() - start_time
        total_bytes = sum([_get_size_of_value(x) for x in ports_values.values()])
        logger.info("Uploaded %s bytes in %s seconds", total_bytes, elapsed_time)
    finally:
        # clean up possible compressed files
        for file_path in temp_files:
            await async_on_threadpool(
                # pylint: disable=cell-var-from-loop
                lambda: shutil.rmtree(file_path.parent, ignore_errors=True)
            )


async def dispatch_update_for_directory(directory_path: Path) -> None:
    logger.info("Uploading data for directory %s", directory_path)
    # TODO: how to figure out from directory_path which is the correct target to upload
    await upload_outputs(directory_path, [])


# INPUTS section


async def _get_data_from_port(port: Port) -> Tuple[Port, ItemConcreteValue]:
    tag = f"[{port.key}] "
    logger.info("%s transfer started for %s", tag, port.key)
    start_time = time.perf_counter()
    ret = await port.get()
    elapsed_time = time.perf_counter() - start_time
    logger.info("%s transfer completed (=%s) in %3.2fs", tag, ret, elapsed_time)
    if isinstance(ret, Path):
        size_mb = ret.stat().st_size / 1024 / 1024
        logger.info(
            "%s %s: data size: %sMB, transfer rate %sMB/s",
            tag,
            ret.name,
            size_mb,
            size_mb / elapsed_time,
        )
    return (port, ret)


async def download_inputs(inputs_path: Path, port_keys: List[str]) -> ByteSize:
    logger.info("retrieving data from simcore...")
    start_time = time.perf_counter()

    settings: DynamicSidecarSettings = get_settings()
    PORTS: Nodeports = await node_ports_v2.ports(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=str(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=str(settings.DY_SIDECAR_NODE_ID),
    )
    data = {}

    # let's gather all the data
    download_tasks = []
    for node_input in (await PORTS.inputs).values():
        # if port_keys contains some keys only download them
        logger.info("Checking node %s", node_input.key)
        if port_keys and node_input.key not in port_keys:
            continue
        # collect coroutines
        download_tasks.append(_get_data_from_port(node_input))
    logger.info("retrieving %s data", len(download_tasks))

    transfer_bytes = 0
    if download_tasks:
        # TODO: limit concurrency to avoid saturating storage+db??
        results: List[Tuple[Port, ItemConcreteValue]] = cast(
            List[Tuple[Port, ItemConcreteValue]], await logged_gather(*download_tasks)
        )
        logger.info("completed download %s", results)
        for port, value in results:

            data[port.key] = {"key": port.key, "value": value}

            if _FILE_TYPE_PREFIX in port.property_type:

                # if there are files, move them to the final destination
                downloaded_file: Optional[Path] = cast(Optional[Path], value)
                dest_path: Path = inputs_path / port.key

                if not downloaded_file or not downloaded_file.exists():
                    # the link may be empty
                    # remove files all files from disk when disconnecting port
                    await remove_directory(dest_path, only_children=True)
                    continue

                transfer_bytes = transfer_bytes + downloaded_file.stat().st_size

                # in case of valid file, it is either uncompressed and/or moved to the final directory
                logger.info("creating directory %s", dest_path)
                dest_path.mkdir(exist_ok=True, parents=True)
                data[port.key] = {"key": port.key, "value": str(dest_path)}

                if zipfile.is_zipfile(downloaded_file):

                    dest_folder = PrunableFolder(dest_path)

                    # unzip updated data to dest_path
                    logger.info("unzipping %s", downloaded_file)
                    unarchived: Set[Path] = await unarchive_dir(
                        archive_to_extract=downloaded_file, destination_folder=dest_path
                    )

                    dest_folder.prune(exclude=unarchived)

                    logger.info("all unzipped in %s", dest_path)
                else:
                    logger.info("moving %s", downloaded_file)
                    dest_path = dest_path / Path(downloaded_file).name
                    await async_on_threadpool(
                        # pylint: disable=cell-var-from-loop
                        lambda: shutil.move(str(downloaded_file), dest_path)
                    )
                    logger.info("all moved to %s", dest_path)
            else:
                transfer_bytes = transfer_bytes + sys.getsizeof(value)

    # create/update the json file with the new values
    if data:
        data_file = inputs_path / _KEY_VALUE_FILE_NAME
        if data_file.exists():
            current_data = json.loads(data_file.read_text())
            # merge data
            data = {**current_data, **data}
        data_file.write_text(json.dumps(data))

    transferred = ByteSize(transfer_bytes)
    elapsed_time = time.perf_counter() - start_time
    logger.info(
        "Downloaded %s in %s seconds",
        transferred.human_readable(decimal=True),
        elapsed_time,
    )

    return transferred


__all__ = ["dispatch_update_for_directory", "upload_outputs", "download_inputs"]
