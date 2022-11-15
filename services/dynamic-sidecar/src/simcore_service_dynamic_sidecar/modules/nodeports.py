import json
import logging
import os
import shutil
import sys
import time
from collections import deque
from contextlib import AsyncExitStack
from enum import Enum
from pathlib import Path
from typing import Any, Coroutine, Optional, cast

import magic
from aiofiles.tempfile import TemporaryDirectory as AioTemporaryDirectory
from models_library.projects import ProjectIDStr
from models_library.projects_nodes import OutputsDict
from models_library.projects_nodes_io import NodeIDStr
from pydantic import ByteSize
from servicelib.archiving_utils import PrunableFolder, archive_dir, unarchive_dir
from servicelib.async_utils import run_sequentially_in_context
from servicelib.file_utils import remove_directory
from servicelib.pools import async_on_threadpool
from servicelib.utils import logged_gather
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB
from simcore_sdk.node_ports_v2 import Nodeports, Port
from simcore_sdk.node_ports_v2.links import ItemConcreteValue
from simcore_sdk.node_ports_v2.port import SetKWargs
from simcore_service_dynamic_sidecar.core.settings import (
    ApplicationSettings,
    get_settings,
)


class PortTypeName(str, Enum):
    INPUTS = "inputs"
    OUTPUTS = "outputs"


_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

logger = logging.getLogger(__name__)

# OUTPUTS section


def _get_size_of_value(value: Optional[ItemConcreteValue]) -> int:
    if value is None:
        return 0
    if isinstance(value, Path):
        # if symlink we need to fetch the pointer to the file
        # relative symlink need to know which their parent is
        # in oder to properly resolve the path since the workdir
        # does not equal to their parent dir
        path = value
        if value.is_symlink():
            path = Path(value.parent) / Path(os.readlink(value))
        size_bytes = path.stat().st_size
        return size_bytes
    return sys.getsizeof(value)


_CONTROL_TESTMARK_DY_SIDECAR_NODEPORT_UPLOADED_MESSAGE = (
    "TEST: test_nodeports_integration DO NOT REMOVE"
)


# NOTE: outputs_manager guarantees that no parallel calls
# to this function occur
async def upload_outputs(
    outputs_path: Path,
    port_keys: list[str],
    io_log_redirect_cb: Optional[LogRedirectCB],
) -> None:
    # pylint: disable=too-many-branches
    logger.debug("uploading data to simcore...")
    start_time = time.perf_counter()

    settings: ApplicationSettings = get_settings()
    PORTS: Nodeports = await node_ports_v2.ports(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=ProjectIDStr(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=NodeIDStr(settings.DY_SIDECAR_NODE_ID),
        r_clone_settings=settings.rclone_settings_for_nodeports,
        io_log_redirect_cb=io_log_redirect_cb,
    )

    # let's gather the tasks
    ports_values: dict[
        str, tuple[Optional[ItemConcreteValue], Optional[SetKWargs]]
    ] = {}
    archiving_tasks: deque[Coroutine[None, None, None]] = deque()

    async with AsyncExitStack() as stack:
        for port in (await PORTS.outputs).values():
            logger.debug("Checking port %s", port.key)
            if port_keys and port.key not in port_keys:
                continue

            if _FILE_TYPE_PREFIX in port.property_type:
                src_folder = outputs_path / port.key
                files_and_folders_list = list(src_folder.rglob("*"))
                logger.debug("Discovered files to upload %s", files_and_folders_list)

                if not files_and_folders_list:
                    ports_values[port.key] = (None, None)
                    continue

                if len(files_and_folders_list) == 1 and (
                    files_and_folders_list[0].is_file()
                    or files_and_folders_list[0].is_symlink()
                ):
                    # special case, direct upload
                    ports_values[port.key] = (
                        files_and_folders_list[0],
                        SetKWargs(
                            file_base_path=(
                                src_folder.parent.relative_to(outputs_path.parent)
                            )
                        ),
                    )
                    continue

                # generic case let's create an archive
                # only the filtered out files will be zipped
                tmp_folder = Path(
                    await stack.enter_async_context(AioTemporaryDirectory())
                )
                tmp_file = tmp_folder / f"{src_folder.stem}.zip"

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
                ports_values[port.key] = (
                    tmp_file,
                    SetKWargs(
                        file_base_path=(
                            src_folder.parent.relative_to(outputs_path.parent)
                        )
                    ),
                )
            else:
                data_file = outputs_path / _KEY_VALUE_FILE_NAME
                if data_file.exists():
                    data = json.loads(data_file.read_text())
                    if port.key in data and data[port.key] is not None:
                        ports_values[port.key] = (data[port.key], None)
                    else:
                        logger.debug("Port %s not found in %s", port.key, data)
                else:
                    logger.debug("No file %s to fetch port values from", data_file)

        if archiving_tasks:
            await logged_gather(*archiving_tasks)

        await PORTS.set_multiple(ports_values)

        elapsed_time = time.perf_counter() - start_time
        total_bytes = sum(_get_size_of_value(x) for x in ports_values.values())
        logger.info("Uploaded %s bytes in %s seconds", total_bytes, elapsed_time)
        logger.debug(_CONTROL_TESTMARK_DY_SIDECAR_NODEPORT_UPLOADED_MESSAGE)


# INPUTS section


def _is_zip_file(file_path: Path) -> bool:
    mime_type = magic.from_file(file_path, mime=True)
    return f"{mime_type}" == "application/zip"


async def _get_data_from_port(port: Port) -> tuple[Port, Optional[ItemConcreteValue]]:
    tag = f"[{port.key}] "
    logger.debug("%s transfer started for %s", tag, port.key)
    start_time = time.perf_counter()
    ret = await port.get()
    elapsed_time = time.perf_counter() - start_time
    logger.debug("%s transfer completed (=%s) in %3.2fs", tag, ret, elapsed_time)
    if isinstance(ret, Path):
        size_mb = ret.stat().st_size / 1024 / 1024
        logger.debug(
            "%s %s: data size: %sMB, transfer rate %sMB/s",
            tag,
            ret.name,
            size_mb,
            size_mb / elapsed_time,
        )
    return port, ret


async def _download_files(
    target_path: Path, download_tasks: deque[Coroutine[Any, int, Any]]
) -> tuple[OutputsDict, ByteSize]:
    transferred_bytes = 0
    data: OutputsDict = {}

    if not download_tasks:
        return data, ByteSize(transferred_bytes)

    # TODO: limit concurrency to avoid saturating storage+db??
    results: list[tuple[Port, ItemConcreteValue]] = cast(
        list[tuple[Port, ItemConcreteValue]], await logged_gather(*download_tasks)
    )
    logger.debug("completed download %s", results)
    for port, value in results:

        data[port.key] = {"key": port.key, "value": value}

        if _FILE_TYPE_PREFIX in port.property_type:

            # if there are files, move them to the final destination
            downloaded_file: Optional[Path] = cast(Optional[Path], value)
            dest_path: Path = target_path / port.key

            if not downloaded_file or not downloaded_file.exists():
                # the link may be empty
                # remove files all files from disk when disconnecting port
                logger.debug("removing contents of dir %s", dest_path)
                await remove_directory(
                    dest_path, only_children=True, ignore_errors=True
                )
                continue

            transferred_bytes = transferred_bytes + downloaded_file.stat().st_size

            # in case of valid file, it is either uncompressed and/or moved to the final directory
            logger.debug("creating directory %s", dest_path)
            dest_path.mkdir(exist_ok=True, parents=True)
            data[port.key] = {"key": port.key, "value": str(dest_path)}

            dest_folder = PrunableFolder(dest_path)

            if _is_zip_file(downloaded_file):
                # unzip updated data to dest_path
                logger.debug("unzipping %s", downloaded_file)
                unarchived: set[Path] = await unarchive_dir(
                    archive_to_extract=downloaded_file, destination_folder=dest_path
                )

                dest_folder.prune(exclude=unarchived)

                logger.debug("all unzipped in %s", dest_path)
            else:
                logger.debug("moving %s", downloaded_file)
                dest_path = dest_path / Path(downloaded_file).name
                await async_on_threadpool(
                    # pylint: disable=cell-var-from-loop
                    lambda: shutil.move(str(downloaded_file), dest_path)
                )

                # NOTE: after the download the current value of the port
                # makes sure previously downloaded files are removed
                dest_folder.prune(exclude={dest_path})

                logger.debug("all moved to %s", dest_path)
        else:
            transferred_bytes = transferred_bytes + sys.getsizeof(value)

    return data, ByteSize(transferred_bytes)


@run_sequentially_in_context()
async def download_target_ports(
    port_type_name: PortTypeName,
    target_path: Path,
    port_keys: list[str],
    io_log_redirect_cb: LogRedirectCB,
) -> ByteSize:
    logger.debug("retrieving data from simcore...")
    start_time = time.perf_counter()

    settings: ApplicationSettings = get_settings()
    PORTS: Nodeports = await node_ports_v2.ports(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=ProjectIDStr(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=NodeIDStr(settings.DY_SIDECAR_NODE_ID),
        r_clone_settings=settings.rclone_settings_for_nodeports,
        io_log_redirect_cb=io_log_redirect_cb,
    )

    # let's gather all the data
    download_tasks: deque[Coroutine[Any, int, Any]] = deque()
    for port_value in (await getattr(PORTS, port_type_name.value)).values():
        # if port_keys contains some keys only download them
        logger.debug("Checking node %s", port_value.key)
        if port_keys and port_value.key not in port_keys:
            continue
        # collect coroutines
        download_tasks.append(_get_data_from_port(port_value))
    logger.debug("retrieving %s data", len(download_tasks))

    data, transferred_bytes = await _download_files(target_path, download_tasks)

    # create/update the json file with the new values
    if data:
        data_file = target_path / _KEY_VALUE_FILE_NAME
        if data_file.exists():
            current_data = json.loads(data_file.read_text())
            # merge data
            data = {**current_data, **data}
        data_file.write_text(json.dumps(data))

    elapsed_time = time.perf_counter() - start_time
    logger.info(
        "Downloaded %s in %s seconds",
        transferred_bytes.human_readable(decimal=True),
        elapsed_time,
    )
    return transferred_bytes
