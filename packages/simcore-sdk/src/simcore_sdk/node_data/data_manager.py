import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, StorageFileID
from models_library.service_settings_labels import LegacyState
from models_library.users import UserID
from pydantic import NonNegativeInt, TypeAdapter
from servicelib.archiving_utils import unarchive_dir
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData
from settings_library.r_clone import RCloneSettings

from ..node_ports_common import filemanager
from ..node_ports_common.constants import SIMCORE_LOCATION
from ..node_ports_common.dbmanager import DBManager
from ..node_ports_common.file_io_utils import LogRedirectCB
from ..node_ports_common.r_clone_mount import MountRemoteType, RCloneMountManager

_logger = logging.getLogger(__name__)


def __create_s3_object_key(project_id: ProjectID, node_id: NodeID, file_path: Path | str) -> StorageFileID:
    file_name = file_path.name if isinstance(file_path, Path) else file_path
    return TypeAdapter(StorageFileID).validate_python(f"{project_id}/{node_id}/{file_name}")


def __get_s3_name(path: Path, *, is_archive: bool) -> str:
    return f"{path.stem}.zip" if is_archive else path.stem


async def _push_directory(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    source_path: Path,
    *,
    io_log_redirect_cb: LogRedirectCB,
    r_clone_settings: RCloneSettings,
    exclude_patterns: set[str] | None = None,
    progress_bar: ProgressBarData,
) -> None:
    s3_object = __create_s3_object_key(project_id, node_id, source_path)
    with log_context(_logger, logging.INFO, f"uploading {source_path.name} to S3 to {s3_object}"):
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


async def _pull_directory(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    destination_path: Path,
    *,
    io_log_redirect_cb: LogRedirectCB,
    r_clone_settings: RCloneSettings,
    progress_bar: ProgressBarData,
    save_to: Path | None = None,
) -> None:
    save_to_path = destination_path if save_to is None else save_to
    s3_object = __create_s3_object_key(project_id, node_id, destination_path)
    with log_context(_logger, logging.INFO, f"pulling data from {s3_object} to {save_to_path}"):
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


async def _pull_legacy_archive(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    destination_path: Path,
    *,
    io_log_redirect_cb: LogRedirectCB,
    progress_bar: ProgressBarData,
    legacy_destination_path: Path | None = None,
) -> None:
    # NOTE: the legacy way of storing states was as zip archives
    archive_path = legacy_destination_path or destination_path
    async with progress_bar.sub_progress(steps=2, description=f"pulling {archive_path.name}") as sub_prog:
        with TemporaryDirectory() as tmp_dir_name:
            archive_file = Path(tmp_dir_name) / __get_s3_name(archive_path, is_archive=True)

            s3_object = __create_s3_object_key(project_id, node_id, archive_file)
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
            _logger.info("completed pull of %s.", archive_path)

            if io_log_redirect_cb:
                await io_log_redirect_cb(f"unarchiving {downloaded_file} into {destination_path}, please wait...")
            await unarchive_dir(
                archive_to_extract=downloaded_file,
                destination_folder=destination_path,
                progress_bar=sub_prog,
                log_cb=io_log_redirect_cb,
            )
            if io_log_redirect_cb:
                await io_log_redirect_cb(f"unarchiving {downloaded_file} into {destination_path} completed.")


async def _state_metadata_entry_exists(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    path: Path,
    *,
    is_archive: bool,
) -> bool:
    """
    :returns True if an entry is present inside the files_metadata else False
    """
    s3_object = __create_s3_object_key(project_id, node_id, __get_s3_name(path, is_archive=is_archive))
    _logger.debug("Checking if s3_object='%s' is present", s3_object)
    return await filemanager.entry_exists(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        s3_object=s3_object,
        is_directory=not is_archive,
    )


async def _delete_legacy_archive(project_id: ProjectID, node_id: NodeID, path: Path, *, application_name: str) -> None:
    """removes the .zip state archive from storage"""
    s3_object = __create_s3_object_key(project_id, node_id, __get_s3_name(path, is_archive=True))
    _logger.debug("Deleting s3_object='%s' is archive", s3_object)

    # NOTE: if service is opened by a person which the users shared it with,
    # they will not have the permission to delete the node
    # Removing it via it's owner allows to always have access to the delete operation.
    owner_id = await DBManager(application_name=application_name).get_project_owner_user_id(project_id)
    await filemanager.delete_file(user_id=owner_id, store_id=SIMCORE_LOCATION, s3_object=s3_object)


async def _stop_mount(mount_manager: RCloneMountManager, destination_path: Path, index: NonNegativeInt) -> None:
    await mount_manager.ensure_unmounted(destination_path, index)


async def push(  # pylint: disable=too-many-arguments  # noqa: PLR0913
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    source_path: Path,
    index: NonNegativeInt,
    *,
    io_log_redirect_cb: LogRedirectCB,
    r_clone_settings: RCloneSettings,
    exclude_patterns: set[str] | None = None,
    progress_bar: ProgressBarData,
    legacy_state: LegacyState | None,
    application_name: str,
    mount_manager: RCloneMountManager,
) -> None:
    """pushes and removes the legacy archive if present"""

    if mount_manager.is_mount_tracked(source_path, index):
        await _stop_mount(mount_manager, source_path, index)
    else:
        await _push_directory(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            source_path=source_path,
            r_clone_settings=r_clone_settings,
            exclude_patterns=exclude_patterns,
            io_log_redirect_cb=io_log_redirect_cb,
            progress_bar=progress_bar,
        )

    archive_exists = await _state_metadata_entry_exists(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        path=source_path,
        is_archive=True,
    )
    if archive_exists:
        with log_context(_logger, logging.INFO, "removing legacy archive"):
            await _delete_legacy_archive(
                project_id=project_id,
                node_id=node_id,
                path=source_path,
                application_name=application_name,
            )

    if legacy_state:
        legacy_archive_exists = await _state_metadata_entry_exists(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            path=legacy_state.old_state_path,
            is_archive=True,
        )
        if legacy_archive_exists:
            with log_context(_logger, logging.INFO, f"removing legacy archive in {legacy_state}"):
                await _delete_legacy_archive(
                    project_id=project_id,
                    node_id=node_id,
                    path=legacy_state.old_state_path,
                    application_name=application_name,
                )


async def _start_mount_if_required(
    mount_manager: RCloneMountManager,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    destination_path: Path,
    index: NonNegativeInt,
    *,
    requires_data_mounting: bool,
) -> None:
    if not requires_data_mounting:
        return

    s3_object = __create_s3_object_key(project_id, node_id, destination_path)

    await filemanager.create_r_clone_mounted_directory_entry(
        user_id=user_id, s3_object=s3_object, store_id=SIMCORE_LOCATION
    )

    await mount_manager.ensure_mounted(
        destination_path,
        index,
        node_id=node_id,
        remote_type=MountRemoteType.S3,
        remote_path=s3_object,
    )


async def pull(  # pylint: disable=too-many-arguments
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    destination_path: Path,
    index: NonNegativeInt,
    *,
    io_log_redirect_cb: LogRedirectCB,
    r_clone_settings: RCloneSettings,
    progress_bar: ProgressBarData,
    legacy_state: LegacyState | None,
    mount_manager: RCloneMountManager,
) -> None:
    """restores the state folder"""

    requires_data_mounting = await mount_manager.delegate.requires_data_mounting()

    if legacy_state and legacy_state.new_state_path == destination_path:
        _logger.info(
            "trying to restore from legacy_state=%s, destination_path=%s",
            legacy_state,
            destination_path,
        )
        legacy_state_exists = await _state_metadata_entry_exists(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            path=legacy_state.old_state_path,
            is_archive=True,
        )
        _logger.info("legacy_state_exists=%s", legacy_state_exists)
        if legacy_state_exists:
            with log_context(
                _logger,
                logging.INFO,
                f"restoring data from legacy archive in {legacy_state}",
            ):
                await _pull_legacy_archive(
                    user_id=user_id,
                    project_id=project_id,
                    node_id=node_id,
                    destination_path=legacy_state.new_state_path,
                    io_log_redirect_cb=io_log_redirect_cb,
                    progress_bar=progress_bar,
                    legacy_destination_path=legacy_state.old_state_path,
                )
                await _start_mount_if_required(
                    mount_manager,
                    user_id,
                    project_id,
                    node_id,
                    destination_path,
                    index,
                    requires_data_mounting=requires_data_mounting,
                )
            return

    state_archive_exists = await _state_metadata_entry_exists(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        path=destination_path,
        is_archive=True,
    )
    if state_archive_exists:
        with log_context(_logger, logging.INFO, "restoring data from legacy archive"):
            await _pull_legacy_archive(
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                destination_path=destination_path,
                io_log_redirect_cb=io_log_redirect_cb,
                progress_bar=progress_bar,
            )
            await _start_mount_if_required(
                mount_manager,
                user_id,
                project_id,
                node_id,
                destination_path,
                index,
                requires_data_mounting=requires_data_mounting,
            )
        return

    state_directory_exists = await _state_metadata_entry_exists(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        path=destination_path,
        is_archive=False,
    )
    if state_directory_exists:
        if requires_data_mounting:
            await _start_mount_if_required(
                mount_manager,
                user_id,
                project_id,
                node_id,
                destination_path,
                index,
                requires_data_mounting=requires_data_mounting,
            )
        else:
            await _pull_directory(
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                destination_path=destination_path,
                io_log_redirect_cb=io_log_redirect_cb,
                r_clone_settings=r_clone_settings,
                progress_bar=progress_bar,
            )

        return

    await _start_mount_if_required(
        mount_manager,
        user_id,
        project_id,
        node_id,
        destination_path,
        index,
        requires_data_mounting=requires_data_mounting,
    )
    _logger.debug("No content previously saved for '%s'", destination_path)
