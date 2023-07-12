import logging
from contextlib import AsyncExitStack
from pathlib import Path
from shutil import move
from tempfile import TemporaryDirectory

from models_library.projects_nodes_io import StorageFileID
from pydantic import parse_obj_as
from servicelib.archiving_utils import archive_dir, unarchive_dir
from servicelib.logging_utils import log_catch, log_context
from servicelib.progress_bar import ProgressBarData
from settings_library.r_clone import RCloneSettings

from ..node_ports_common import filemanager
from ..node_ports_common.constants import SIMCORE_LOCATION
from ..node_ports_common.file_io_utils import LogRedirectCB

log = logging.getLogger(__name__)


def _create_s3_object(
    project_id: str, node_uuid: str, file_path: Path | str
) -> StorageFileID:
    file_name = file_path.name if isinstance(file_path, Path) else file_path
    return parse_obj_as(StorageFileID, f"{project_id}/{node_uuid}/{file_name}")


async def _push_file(
    user_id: int,
    project_id: str,
    node_uuid: str,
    file_path: Path,
    *,
    rename_to: str | None,
    io_log_redirect_cb: LogRedirectCB | None,
    r_clone_settings: RCloneSettings | None = None,
    progress_bar: ProgressBarData,
) -> None:
    store_id = SIMCORE_LOCATION
    s3_object = _create_s3_object(
        project_id, node_uuid, rename_to if rename_to else file_path
    )
    log.info("uploading %s to S3 to %s...", file_path.name, s3_object)
    await filemanager.upload_path(
        user_id=user_id,
        store_id=store_id,
        store_name=None,
        s3_object=s3_object,
        path_to_upload=file_path,
        r_clone_settings=r_clone_settings,
        io_log_redirect_cb=io_log_redirect_cb,
        progress_bar=progress_bar,
    )
    log.info("%s successfuly uploaded", file_path)


async def push(
    user_id: int,
    project_id: str,
    node_uuid: str,
    file_or_folder: Path,
    *,
    io_log_redirect_cb: LogRedirectCB | None,
    rename_to: str | None = None,
    r_clone_settings: RCloneSettings | None = None,
    archive_exclude_patterns: set[str] | None = None,
    progress_bar: ProgressBarData,
) -> None:
    if file_or_folder.is_file():
        await _push_file(
            user_id,
            project_id,
            node_uuid,
            file_or_folder,
            rename_to=rename_to,
            io_log_redirect_cb=io_log_redirect_cb,
            progress_bar=progress_bar,
        )
        return
    # NOTE: the when pushing the state of the directories, the zipping will be removed
    async with AsyncExitStack() as stack:
        stack.enter_context(log_catch(log))
        stack.enter_context(
            log_context(log, logging.INFO, "pushing %s", file_or_folder)
        )
        tmp_dir_name = stack.enter_context(
            TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        sub_progress = await stack.enter_async_context(
            progress_bar.sub_progress(steps=2)
        )

        # compress the files
        archive_file_path = (
            Path(tmp_dir_name) / f"{rename_to or file_or_folder.stem}.zip"
        )
        if io_log_redirect_cb:
            await io_log_redirect_cb(
                f"archiving {file_or_folder} into {archive_file_path}, please wait..."
            )
        await archive_dir(
            dir_to_compress=file_or_folder,
            destination=archive_file_path,
            compress=False,  # disabling compression for faster speeds
            store_relative_path=True,
            exclude_patterns=archive_exclude_patterns,
            progress_bar=sub_progress,
        )
        if io_log_redirect_cb:
            await io_log_redirect_cb(
                f"archiving {file_or_folder} into {archive_file_path} completed."
            )
        await _push_file(
            user_id,
            project_id,
            node_uuid,
            archive_file_path,
            rename_to=None,
            r_clone_settings=r_clone_settings,
            io_log_redirect_cb=io_log_redirect_cb,
            progress_bar=sub_progress,
        )


async def _pull_file(
    user_id: int,
    project_id: str,
    node_uuid: str,
    file_path: Path,
    *,
    io_log_redirect_cb: LogRedirectCB | None,
    save_to: Path | None = None,
    r_clone_settings: RCloneSettings | None,
    progress_bar: ProgressBarData,
) -> None:
    destination_path = file_path if save_to is None else save_to
    s3_object = _create_s3_object(project_id, node_uuid, file_path)
    log.info("pulling data from %s to %s...", s3_object, file_path)
    downloaded_file = await filemanager.download_path_from_s3(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        store_name=None,
        s3_object=s3_object,
        local_folder=destination_path.parent,
        io_log_redirect_cb=io_log_redirect_cb,
        r_clone_settings=r_clone_settings,
        progress_bar=progress_bar,
    )
    if downloaded_file != destination_path:
        destination_path.unlink(missing_ok=True)
        move(f"{downloaded_file}", destination_path)
    log.info("completed pull of %s.", destination_path)


def _get_archive_name(path: Path) -> str:
    return f"{path.stem}.zip"


async def pull(
    user_id: int,
    project_id: str,
    node_uuid: str,
    file_or_folder: Path,
    *,
    io_log_redirect_cb: LogRedirectCB | None,
    save_to: Path | None = None,
    r_clone_settings: RCloneSettings | None,
    progress_bar: ProgressBarData,
) -> None:
    if file_or_folder.is_file():
        await _pull_file(
            user_id,
            project_id,
            node_uuid,
            file_or_folder,
            save_to=save_to,
            io_log_redirect_cb=io_log_redirect_cb,
            r_clone_settings=r_clone_settings,
            progress_bar=progress_bar,
        )
        return
    # NOTE: the when pulling the state of the directories, the zipping will be removed
    # we have a folder, so we need somewhere to extract it to
    async with progress_bar.sub_progress(steps=2) as sub_prog:
        with TemporaryDirectory() as tmp_dir_name:
            archive_file = Path(tmp_dir_name) / _get_archive_name(file_or_folder)
            await _pull_file(
                user_id,
                project_id,
                node_uuid,
                archive_file,
                io_log_redirect_cb=io_log_redirect_cb,
                r_clone_settings=r_clone_settings,
                progress_bar=sub_prog,
            )

            destination_folder = file_or_folder if save_to is None else save_to
            if io_log_redirect_cb:
                await io_log_redirect_cb(
                    f"unarchiving {archive_file} into {destination_folder}, please wait..."
                )
            await unarchive_dir(
                archive_to_extract=archive_file,
                destination_folder=destination_folder,
                progress_bar=sub_prog,
                log_cb=io_log_redirect_cb,
            )
            if io_log_redirect_cb:
                await io_log_redirect_cb(
                    f"unarchiving {archive_file} into {destination_folder} completed."
                )


async def exists(
    user_id: int, project_id: str, node_uuid: str, file_path: Path
) -> bool:
    """
    :returns True if an entry is present inside the files_metadata else False
    """
    s3_object = _create_s3_object(project_id, node_uuid, _get_archive_name(file_path))
    log.debug("Checking if s3_object='%s' is present", s3_object)
    return await filemanager.entry_exists(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        s3_object=s3_object,
    )
