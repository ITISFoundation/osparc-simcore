import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, StorageFileID
from models_library.users import UserID
from pydantic import parse_obj_as
from servicelib.archiving_utils import unarchive_dir
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData
from settings_library.r_clone import RCloneSettings

from ..node_ports_common import filemanager
from ..node_ports_common.constants import SIMCORE_LOCATION
from ..node_ports_common.file_io_utils import LogRedirectCB

_logger = logging.getLogger(__name__)


def _create_s3_object_key(
    project_id: ProjectID, node_uuid: NodeID, file_path: Path | str
) -> StorageFileID:
    file_name = file_path.name if isinstance(file_path, Path) else file_path
    return parse_obj_as(StorageFileID, f"{project_id}/{node_uuid}/{file_name}")


async def push_directory(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    source_path: Path,
    *,
    io_log_redirect_cb: LogRedirectCB,
    r_clone_settings: RCloneSettings,
    exclude_patterns: set[str] | None = None,
    progress_bar: ProgressBarData,
) -> None:
    s3_object = _create_s3_object_key(project_id, node_uuid, source_path)
    _logger.info("uploading %s to S3 to %s...", source_path.name, s3_object)
    await filemanager.upload_path(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        store_name=None,
        s3_object=s3_object,
        path_to_upload=source_path,
        r_clone_settings=r_clone_settings,
        io_log_redirect_cb=io_log_redirect_cb,
        progress_bar=progress_bar,
        exclude_patterns=exclude_patterns,
    )
    _logger.info("%s successfully uploaded", source_path)


def _get_s3_name(path: Path, *, is_archive: bool) -> str:
    return f"{path.stem}.zip" if is_archive else path.stem


async def pull_directory(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    destination_path: Path,
    *,
    io_log_redirect_cb: LogRedirectCB,
    save_to: Path | None = None,
    r_clone_settings: RCloneSettings,
    progress_bar: ProgressBarData,
) -> None:
    save_to_path = destination_path if save_to is None else save_to
    s3_object = _create_s3_object_key(project_id, node_uuid, destination_path)
    with log_context(
        _logger, logging.INFO, f"pulling data from {s3_object} to {save_to_path}..."
    ):
        await filemanager.download_path_from_s3(
            user_id=user_id,
            store_id=SIMCORE_LOCATION,
            store_name=None,
            s3_object=s3_object,
            local_path=save_to_path,
            io_log_redirect_cb=io_log_redirect_cb,
            r_clone_settings=r_clone_settings,
            progress_bar=progress_bar,
        )


async def pull_legacy_archive(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    destination_path: Path,
    *,
    io_log_redirect_cb: LogRedirectCB,
    progress_bar: ProgressBarData,
) -> None:
    # NOTE: the legacy way of storing states was as zip archives
    async with progress_bar.sub_progress(steps=2) as sub_prog:
        with TemporaryDirectory() as tmp_dir_name:
            archive_file = Path(tmp_dir_name) / _get_s3_name(
                destination_path, is_archive=True
            )

            s3_object = _create_s3_object_key(project_id, node_uuid, archive_file)
            _logger.info("pulling data from %s to %s...", s3_object, archive_file)
            downloaded_file = await filemanager.download_path_from_s3(
                user_id=user_id,
                store_id=SIMCORE_LOCATION,
                store_name=None,
                s3_object=s3_object,
                local_path=archive_file.parent,
                io_log_redirect_cb=io_log_redirect_cb,
                r_clone_settings=None,
                progress_bar=sub_prog,
            )
            _logger.info("completed pull of %s.", destination_path)

            if io_log_redirect_cb:
                await io_log_redirect_cb(
                    f"unarchiving {downloaded_file} into {destination_path}, please wait..."
                )
            await unarchive_dir(
                archive_to_extract=downloaded_file,
                destination_folder=destination_path,
                progress_bar=sub_prog,
                log_cb=io_log_redirect_cb,
            )
            if io_log_redirect_cb:
                await io_log_redirect_cb(
                    f"unarchiving {downloaded_file} into {destination_path} completed."
                )


async def state_metadata_entry_exists(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    path: Path,
    *,
    is_archive: bool,
) -> bool:
    """
    :returns True if an entry is present inside the files_metadata else False
    """
    s3_object = _create_s3_object_key(
        project_id, node_uuid, _get_s3_name(path, is_archive=is_archive)
    )
    _logger.debug("Checking if s3_object='%s' is present", s3_object)
    return await filemanager.entry_exists(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        s3_object=s3_object,
        is_directory=not is_archive,
    )


async def delete_legacy_archive(
    user_id: UserID, project_id: ProjectID, node_uuid: NodeID, path: Path
) -> None:
    """removes the .zip state archive from storage"""
    s3_object = _create_s3_object_key(
        project_id, node_uuid, _get_s3_name(path, is_archive=True)
    )
    _logger.debug("Deleting s3_object='%s' is archive", s3_object)
    await filemanager.delete_file(
        user_id=user_id, store_id=SIMCORE_LOCATION, s3_object=s3_object
    )
