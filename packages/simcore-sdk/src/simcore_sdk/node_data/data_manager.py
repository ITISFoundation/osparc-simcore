import logging
from pathlib import Path
from shutil import move
from tempfile import TemporaryDirectory
from typing import Optional, Union

from servicelib.archiving_utils import archive_dir, unarchive_dir

from ..node_ports_common import filemanager

log = logging.getLogger(__name__)


def _create_s3_object(
    project_id: str, node_uuid: str, file_path: Union[Path, str]
) -> str:
    file_name = file_path.name if isinstance(file_path, Path) else file_path
    return f"{project_id}/{node_uuid}/{file_name}"


async def _push_file(
    user_id: int,
    project_id: str,
    node_uuid: str,
    file_path: Path,
    rename_to: Optional[str],
):
    store_id = "0"  # this is for simcore.s3
    s3_object = _create_s3_object(
        project_id, node_uuid, rename_to if rename_to else file_path
    )
    log.info("uploading %s to S3 to %s...", file_path.name, s3_object)
    await filemanager.upload_file(
        user_id=user_id,
        store_id=store_id,
        store_name=None,
        s3_object=s3_object,
        local_file_path=file_path,
    )
    log.info("%s successfuly uploaded", file_path)


async def push(
    user_id: int,
    project_id: str,
    node_uuid: str,
    file_or_folder: Path,
    rename_to: Optional[str] = None,
):
    if file_or_folder.is_file():
        return await _push_file(
            user_id, project_id, node_uuid, file_or_folder, rename_to
        )
    # we have a folder, so we create a compressed file
    with TemporaryDirectory() as tmp_dir_name:
        log.info("compressing %s into %s...", file_or_folder.name, tmp_dir_name)
        # compress the files
        archive_file_path = Path(tmp_dir_name) / (
            "%s.zip" % (rename_to if rename_to else file_or_folder.stem)
        )
        await archive_dir(
            dir_to_compress=file_or_folder,
            destination=archive_file_path,
            compress=False,  # disabling compression for faster speeds
            store_relative_path=True,
        )
        return await _push_file(user_id, project_id, node_uuid, archive_file_path, None)


async def _pull_file(
    user_id: int,
    project_id: str,
    node_uuid: str,
    file_path: Path,
    save_to: Optional[Path] = None,
):
    destination_path = file_path if save_to is None else save_to
    s3_object = _create_s3_object(project_id, node_uuid, file_path)
    log.info("pulling data from %s to %s...", s3_object, file_path)
    downloaded_file = await filemanager.download_file_from_s3(
        user_id=user_id,
        store_id="0",
        store_name=None,
        s3_object=s3_object,
        local_folder=destination_path.parent,
    )
    if downloaded_file != destination_path:
        destination_path.unlink(missing_ok=True)
        move(f"{downloaded_file}", destination_path)
    log.info("%s successfuly pulled", destination_path)


def _get_archive_name(path: Path) -> str:
    return f"{path.stem}.zip"


async def pull(
    user_id: int,
    project_id: str,
    node_uuid: str,
    file_or_folder: Path,
    save_to: Optional[Path] = None,
):
    if file_or_folder.is_file():
        return await _pull_file(user_id, project_id, node_uuid, file_or_folder, save_to)
    # we have a folder, so we need somewhere to extract it to
    with TemporaryDirectory() as tmp_dir_name:
        archive_file = Path(tmp_dir_name) / _get_archive_name(file_or_folder)
        await _pull_file(user_id, project_id, node_uuid, archive_file)
        log.info("extracting data from %s", archive_file)

        destination_folder = file_or_folder if save_to is None else save_to
        await unarchive_dir(
            archive_to_extract=archive_file, destination_folder=destination_folder
        )
        log.info("extraction completed")


async def is_file_present_in_storage(
    user_id: int, project_id: str, node_uuid: str, file_path: Path
) -> bool:
    """
    :returns True if an entry is present inside the files_metadata else False
    """
    s3_object = _create_s3_object(project_id, node_uuid, _get_archive_name(file_path))
    log.debug("Checking if s3_object='%s' is present", s3_object)
    return await filemanager.entry_exists(
        user_id=user_id,
        store_id="0",  # this is for simcore.s3
        s3_object=s3_object,
    )
