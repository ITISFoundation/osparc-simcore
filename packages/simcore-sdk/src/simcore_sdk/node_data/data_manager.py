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
    project_id: str, node_uuid: str, file_path: Path, rename_to: Optional[str]
):
    store_id = "0"  # this is for simcore.s3
    s3_object = _create_s3_object(
        project_id, node_uuid, rename_to if rename_to else file_path
    )
    log.info("uploading %s to S3 to %s...", file_path.name, s3_object)
    await filemanager.upload_file(
        store_id=store_id, s3_object=s3_object, local_file_path=file_path
    )
    log.info("%s successfuly uploaded", file_path)


async def push(
    project_id: str,
    node_uuid: str,
    file_or_folder: Path,
    rename_to: Optional[str] = None,
):
    if file_or_folder.is_file():
        return await _push_file(project_id, node_uuid, file_or_folder, rename_to)
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
        return await _push_file(project_id, node_uuid, archive_file_path, None)


async def _pull_file(project_id: str, node_uuid: str, file_path: Path):
    s3_object = _create_s3_object(project_id, node_uuid, file_path)
    log.info("pulling data from %s to %s...", s3_object, file_path)
    downloaded_file = await filemanager.download_file_from_s3(
        store_id="0", s3_object=s3_object, local_folder=file_path.parent
    )
    if downloaded_file != file_path:
        if file_path.exists():
            file_path.unlink()
        move(f"{downloaded_file}", file_path)
    log.info("%s successfuly pulled", file_path)


def _get_archive_name(path: Path) -> str:
    return f"{path.stem}.zip"


async def pull(project_id: str, node_uuid: str, file_or_folder: Path):
    if file_or_folder.is_file():
        return await _pull_file(project_id, node_uuid, file_or_folder)
    # we have a folder, so we need somewhere to extract it to
    with TemporaryDirectory() as tmp_dir_name:
        archive_file = Path(tmp_dir_name) / _get_archive_name(file_or_folder)
        await _pull_file(project_id, node_uuid, archive_file)
        log.info("extracting data from %s", archive_file)
        await unarchive_dir(
            archive_to_extract=archive_file, destination_folder=file_or_folder
        )
        log.info("extraction completed")


async def is_file_present_in_storage(
    project_id: str, node_uuid: str, file_path: Path
) -> bool:
    """
    :returns True if an entry is present inside the files_metadata else False
    """
    s3_object = _create_s3_object(project_id, node_uuid, _get_archive_name(file_path))
    log.debug("Checking if s3_object='%s' is present", s3_object)
    return await filemanager.entry_exists(
        store_id="0",  # this is for simcore.s3
        s3_object=s3_object,
    )
