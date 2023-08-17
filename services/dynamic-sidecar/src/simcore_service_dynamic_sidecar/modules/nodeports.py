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
from typing import Coroutine, Optional, cast

import aiofiles.os
import magic
from aiofiles.tempfile import TemporaryDirectory as AioTemporaryDirectory
from models_library.projects import ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from pydantic import ByteSize
from servicelib.archiving_utils import PrunableFolder, archive_dir, unarchive_dir
from servicelib.async_utils import run_sequentially_in_context
from servicelib.file_utils import remove_directory
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB
from simcore_sdk.node_ports_v2 import Nodeports, Port
from simcore_sdk.node_ports_v2.links import ItemConcreteValue
from simcore_sdk.node_ports_v2.port import SetKWargs
from simcore_sdk.node_ports_v2.port_utils import is_file_type

from ..core.settings import ApplicationSettings, get_settings


class PortTypeName(str, Enum):
    INPUTS = "inputs"
    OUTPUTS = "outputs"


_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

logger = logging.getLogger(__name__)

# OUTPUTS section


def _get_size_of_value(value: ItemConcreteValue | None) -> int:
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
    io_log_redirect_cb: LogRedirectCB | None,
    progress_bar: ProgressBarData,
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
    ports_values: dict[str, tuple[ItemConcreteValue | None, SetKWargs | None]] = {}
    archiving_tasks: deque[Coroutine[None, None, None]] = deque()
    ports_to_set = [
        port_value
        for port_value in (await PORTS.outputs).values()
        if (not port_keys) or (port_value.key in port_keys)
    ]

    async with AsyncExitStack() as stack:
        sub_progress = await stack.enter_async_context(
            progress_bar.sub_progress(
                steps=sum(
                    2 if is_file_type(port.property_type) else 1
                    for port in ports_to_set
                )
            )
        )
        for port in ports_to_set:
            if is_file_type(port.property_type):
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
                        progress_bar=sub_progress,
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

        await PORTS.set_multiple(ports_values, progress_bar=sub_progress)

        elapsed_time = time.perf_counter() - start_time
        total_bytes = sum(_get_size_of_value(x) for x in ports_values.values())
        logger.info("Uploaded %s bytes in %s seconds", total_bytes, elapsed_time)
        logger.debug(_CONTROL_TESTMARK_DY_SIDECAR_NODEPORT_UPLOADED_MESSAGE)


# INPUTS section


def _is_zip_file(file_path: Path) -> bool:
    mime_type = magic.from_file(file_path, mime=True)
    return f"{mime_type}" == "application/zip"


_shutil_move = aiofiles.os.wrap(shutil.move)


async def _get_data_from_port(
    port: Port, *, target_dir: Path, progress_bar: ProgressBarData
) -> tuple[Port, ItemConcreteValue | None, ByteSize]:
    async with progress_bar.sub_progress(
        steps=2 if is_file_type(port.property_type) else 1
    ) as sub_progress:
        with log_context(logger, logging.DEBUG, f"getting {port.key=}"):
            port_data = await port.get(sub_progress)

        if is_file_type(port.property_type):
            # if there are files, move them to the final destination
            downloaded_file: Path | None = cast(Optional[Path], port_data)
            final_path: Path = target_dir / port.key

            if not downloaded_file or not downloaded_file.exists():
                # the link may be empty
                # remove files all files from disk when disconnecting port
                logger.debug("removing contents of dir %s", final_path)
                await remove_directory(
                    final_path, only_children=True, ignore_errors=True
                )
                return port, None, ByteSize(0)

            transferred_bytes = downloaded_file.stat().st_size

            # in case of valid file, it is either uncompressed and/or moved to the final directory
            with log_context(logger, logging.DEBUG, "creating directory"):
                final_path.mkdir(exist_ok=True, parents=True)
            port_data = f"{final_path}"
            dest_folder = PrunableFolder(final_path)

            if _is_zip_file(downloaded_file):
                # unzip updated data to dest_path
                logger.debug("unzipping %s", downloaded_file)
                unarchived: set[Path] = await unarchive_dir(
                    archive_to_extract=downloaded_file,
                    destination_folder=final_path,
                    progress_bar=sub_progress,
                )

                dest_folder.prune(exclude=unarchived)

                logger.debug("all unzipped in %s", final_path)
            else:
                logger.debug("moving %s", downloaded_file)
                final_path = final_path / Path(downloaded_file).name
                await _shutil_move(str(downloaded_file), final_path)

                # NOTE: after the download the current value of the port
                # makes sure previously downloaded files are removed
                dest_folder.prune(exclude={final_path})

                logger.debug("all moved to %s", final_path)
        else:
            transferred_bytes = sys.getsizeof(port_data)

        return port, port_data, ByteSize(transferred_bytes)


@run_sequentially_in_context()
async def download_target_ports(
    port_type_name: PortTypeName,
    target_dir: Path,
    port_keys: list[str],
    io_log_redirect_cb: LogRedirectCB,
    progress_bar: ProgressBarData,
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
    ports_to_get = [
        port_value
        for port_value in (await getattr(PORTS, port_type_name.value)).values()
        if (not port_keys) or (port_value.key in port_keys)
    ]
    async with progress_bar.sub_progress(steps=len(ports_to_get)) as sub_progress:
        results = await logged_gather(
            *[
                _get_data_from_port(
                    port, target_dir=target_dir, progress_bar=sub_progress
                )
                for port in ports_to_get
            ],
            max_concurrency=2,
        )
    # parse results
    data = {
        port.key: {"key": port.key, "value": port_data}
        for (port, port_data, _) in results
    }
    total_transfered_bytes = ByteSize(
        sum(port_transferred_bytes for *_, port_transferred_bytes in results)
    )

    # create/update the json file with the new values
    if data:
        data_file = target_dir / _KEY_VALUE_FILE_NAME
        if data_file.exists():
            current_data = json.loads(data_file.read_text())
            # merge data
            data = {**current_data, **data}
        data_file.write_text(json.dumps(data))

    elapsed_time = time.perf_counter() - start_time
    logger.info(
        "Downloaded %s in %s seconds",
        total_transfered_bytes.human_readable(decimal=True),
        elapsed_time,
    )
    return total_transfered_bytes
