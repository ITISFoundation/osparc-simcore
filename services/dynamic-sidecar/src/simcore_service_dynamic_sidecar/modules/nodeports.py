import json
import logging
import sys
import time
from asyncio import CancelledError
from collections import deque
from collections.abc import Coroutine
from contextlib import AsyncExitStack
from enum import Enum
from pathlib import Path
from typing import cast

import magic
from aiofiles.os import remove
from aiofiles.tempfile import TemporaryDirectory as AioTemporaryDirectory
from common_library.json_serialization import json_loads
from models_library.projects import ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from models_library.services_types import ServicePortKey
from pydantic import ByteSize, TypeAdapter
from servicelib.archiving_utils import PrunableFolder, archive_dir, unarchive_dir
from servicelib.async_utils import run_sequentially_in_context
from servicelib.file_utils import remove_directory, shutil_move
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import limited_gather
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB
from simcore_sdk.node_ports_v2 import Port
from simcore_sdk.node_ports_v2.links import ItemConcreteValue
from simcore_sdk.node_ports_v2.nodeports_v2 import Nodeports, OutputsCallbacks
from simcore_sdk.node_ports_v2.port import SetKWargs
from simcore_sdk.node_ports_v2.port_utils import is_file_type

from ..core.settings import ApplicationSettings, get_settings
from ..modules.notifications import PortNotifier


class PortTypeName(str, Enum):
    INPUTS = "inputs"
    OUTPUTS = "outputs"


_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

_logger = logging.getLogger(__name__)


def _get_size_of_value(
    value: tuple[ItemConcreteValue | None, SetKWargs | None],
) -> int:
    concrete_value, _ = value
    if concrete_value is None:
        return 0
    if isinstance(concrete_value, Path):
        # if symlink we need to fetch the pointer to the file
        # relative symlink need to know which their parent is
        # in oder to properly resolve the path since the workdir
        # does not equal to their parent dir
        path = concrete_value
        if concrete_value.is_symlink():
            path = Path(concrete_value.parent) / Path(Path.readlink(concrete_value))
        return path.stat().st_size
    return sys.getsizeof(value)


_CONTROL_TESTMARK_DY_SIDECAR_NODEPORT_UPLOADED_MESSAGE = (
    "TEST: test_nodeports_integration DO NOT REMOVE"
)


class OutputCallbacksWrapper(OutputsCallbacks):
    def __init__(self, port_notifier: PortNotifier) -> None:
        self.port_notifier = port_notifier

    async def aborted(self, key: ServicePortKey) -> None:
        await self.port_notifier.send_output_port_upload_was_aborted(key)

    async def finished_succesfully(self, key: ServicePortKey) -> None:
        await self.port_notifier.send_output_port_upload_finished_successfully(key)

    async def finished_with_error(self, key: ServicePortKey) -> None:
        await self.port_notifier.send_output_port_upload_finished_with_error(key)


# NOTE: outputs_manager guarantees that no parallel calls to this function occur
async def upload_outputs(  # pylint:disable=too-many-statements  # noqa: PLR0915, C901
    outputs_path: Path,
    port_keys: list[str],
    io_log_redirect_cb: LogRedirectCB | None,
    progress_bar: ProgressBarData,
    port_notifier: PortNotifier,
) -> None:
    # pylint: disable=too-many-branches
    _logger.debug("uploading data to simcore...")
    start_time = time.perf_counter()

    settings: ApplicationSettings = get_settings()
    PORTS: Nodeports = await node_ports_v2.ports(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=ProjectIDStr(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=TypeAdapter(NodeIDStr).validate_python(
            f"{settings.DY_SIDECAR_NODE_ID}"
        ),
        r_clone_settings=None,
        io_log_redirect_cb=io_log_redirect_cb,
        aws_s3_cli_settings=None,
    )

    # let's gather the tasks
    ports_values: dict[
        ServicePortKey, tuple[ItemConcreteValue | None, SetKWargs | None]
    ] = {}
    archiving_tasks: deque[Coroutine[None, None, None]] = deque()
    ports_to_set: list[Port] = [
        port_value
        for port_value in (await PORTS.outputs).values()
        if (not port_keys) or (port_value.key in port_keys)
    ]

    await limited_gather(
        *(port_notifier.send_output_port_upload_sarted(p.key) for p in ports_to_set),
        limit=4,
    )

    async with AsyncExitStack() as stack:
        sub_progress = await stack.enter_async_context(
            progress_bar.sub_progress(
                steps=sum(
                    2 if is_file_type(port.property_type) else 1
                    for port in ports_to_set
                ),
                description="uploading outputs",
            )
        )
        for port in ports_to_set:
            if is_file_type(port.property_type):
                src_folder = outputs_path / port.key
                files_and_folders_list = list(src_folder.rglob("*"))
                _logger.debug("Discovered files to upload %s", files_and_folders_list)

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
                    await stack.enter_async_context(AioTemporaryDirectory())  # type: ignore[arg-type]
                )
                tmp_file = tmp_folder / f"{src_folder.stem}.zip"

                # when having multiple directories it is important to
                # run the compression in parallel to guarantee better performance
                async def _archive_dir_notified(
                    dir_to_compress: Path, destination: Path, port_key: ServicePortKey
                ) -> None:
                    # Errors and cancellation can also be triggered from archving as well
                    try:
                        await archive_dir(
                            dir_to_compress=dir_to_compress,
                            destination=destination,
                            compress=False,
                            progress_bar=sub_progress,
                        )
                    except CancelledError:
                        await port_notifier.send_output_port_upload_was_aborted(
                            port_key
                        )
                        raise
                    except Exception:
                        await port_notifier.send_output_port_upload_finished_with_error(
                            port_key
                        )
                        raise

                archiving_tasks.append(
                    _archive_dir_notified(
                        dir_to_compress=src_folder,
                        destination=tmp_file,
                        port_key=port.key,
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
                    data = json_loads(data_file.read_text())
                    if port.key in data and data[port.key] is not None:
                        ports_values[port.key] = (data[port.key], None)
                    else:
                        _logger.debug("Port %s not found in %s", port.key, data)
                else:
                    _logger.debug("No file %s to fetch port values from", data_file)

        if archiving_tasks:
            await limited_gather(*archiving_tasks, limit=4)

        await PORTS.set_multiple(
            ports_values,
            progress_bar=sub_progress,
            outputs_callbacks=OutputCallbacksWrapper(port_notifier),
        )

        elapsed_time = time.perf_counter() - start_time
        total_bytes = sum(_get_size_of_value(x) for x in ports_values.values())
        _logger.info("Uploaded %s bytes in %s seconds", total_bytes, elapsed_time)
        _logger.debug(_CONTROL_TESTMARK_DY_SIDECAR_NODEPORT_UPLOADED_MESSAGE)


# INPUTS section


def _is_zip_file(file_path: Path) -> bool:
    mime_type = magic.from_file(file_path, mime=True)
    return f"{mime_type}" == "application/zip"


async def _get_data_from_port(
    port: Port, *, target_dir: Path, progress_bar: ProgressBarData
) -> tuple[Port, ItemConcreteValue | None, ByteSize]:
    async with progress_bar.sub_progress(
        steps=2 if is_file_type(port.property_type) else 1,
        description="getting data",
    ) as sub_progress:
        with log_context(_logger, logging.DEBUG, f"getting {port.key=}"):
            port_data = await port.get(sub_progress)

        if is_file_type(port.property_type):
            # if there are files, move them to the final destination
            downloaded_file: Path | None = cast(Path | None, port_data)
            final_path: Path = target_dir / port.key

            if not downloaded_file or not downloaded_file.exists():
                # the link may be empty
                # remove files all files from disk when disconnecting port
                with log_context(
                    _logger, logging.DEBUG, f"removing contents of dir '{final_path}'"
                ):
                    await remove_directory(
                        final_path, only_children=True, ignore_errors=True
                    )
                return port, None, ByteSize(0)

            transferred_bytes = downloaded_file.stat().st_size

            # in case of valid file, it is either uncompressed and/or moved to the final directory
            with log_context(_logger, logging.DEBUG, "creating directory"):
                final_path.mkdir(exist_ok=True, parents=True)
            port_data = f"{final_path}"

            archive_files: set[Path]

            if _is_zip_file(downloaded_file):
                prunable_folder = PrunableFolder(final_path.parent)
                with log_context(
                    _logger,
                    logging.DEBUG,
                    f"unzipping '{downloaded_file}' to {final_path}",
                ):
                    archive_files = await unarchive_dir(
                        archive_to_extract=downloaded_file,
                        destination_folder=final_path,
                        progress_bar=sub_progress,
                    )

                with log_context(
                    _logger, logging.DEBUG, f"archive removal '{downloaded_file}'"
                ):
                    await remove(downloaded_file)
            else:
                # move archive to directory as is
                final_path = final_path / downloaded_file.name
                prunable_folder = PrunableFolder(final_path.parent)

                with log_context(
                    _logger, logging.DEBUG, f"moving {downloaded_file} to {final_path}"
                ):
                    final_path.parent.mkdir(exist_ok=True, parents=True)
                    await shutil_move(downloaded_file, final_path)

                archive_files = {final_path}

            # NOTE: after the port content changes, make sure old files
            # which are no longer part of the port, are removed
            prunable_folder.prune(exclude=archive_files)
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
    port_notifier: PortNotifier | None,
) -> ByteSize:
    _logger.debug("retrieving data from simcore...")
    start_time = time.perf_counter()

    settings: ApplicationSettings = get_settings()
    PORTS: Nodeports = await node_ports_v2.ports(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=ProjectIDStr(settings.DY_SIDECAR_PROJECT_ID),
        node_uuid=TypeAdapter(NodeIDStr).validate_python(
            f"{settings.DY_SIDECAR_NODE_ID}"
        ),
        r_clone_settings=None,
        io_log_redirect_cb=io_log_redirect_cb,
        aws_s3_cli_settings=None,
    )

    # let's gather all the data
    ports_to_get: list[Port] = [
        port_value
        for port_value in (await getattr(PORTS, port_type_name.value)).values()
        if (not port_keys) or (port_value.key in port_keys)
    ]

    async def _get_date_from_port_notified(
        port: Port, progress_bar: ProgressBarData
    ) -> tuple[Port, ItemConcreteValue | None, ByteSize]:
        assert port_notifier is not None
        await port_notifier.send_input_port_download_started(port.key)
        try:
            result = await _get_data_from_port(
                port, target_dir=target_dir, progress_bar=progress_bar
            )
            await port_notifier.send_input_port_download_finished_succesfully(port.key)
            return result

        except CancelledError:
            await port_notifier.send_input_port_download_was_aborted(port.key)
            raise
        except Exception:
            await port_notifier.send_input_port_download_finished_with_error(port.key)
            raise

    async with progress_bar.sub_progress(
        steps=len(ports_to_get), description="downloading"
    ) as sub_progress:
        results = await limited_gather(
            *[
                (
                    _get_data_from_port(
                        port, target_dir=target_dir, progress_bar=sub_progress
                    )
                    if port_type_name == PortTypeName.OUTPUTS
                    else _get_date_from_port_notified(port, progress_bar=sub_progress)
                )
                for port in ports_to_get
            ],
            limit=2,
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
            current_data = json_loads(data_file.read_text())
            # merge data
            data = {**current_data, **data}
        data_file.write_text(json.dumps(data))

    elapsed_time = time.perf_counter() - start_time
    _logger.info(
        "Downloaded %s in %s seconds",
        total_transfered_bytes.human_readable(decimal=True),
        elapsed_time,
    )
    return total_transfered_bytes
