import logging
from pathlib import Path
from shutil import make_archive, move, unpack_archive
from tempfile import TemporaryDirectory
from typing import Optional, Union

from simcore_sdk.node_ports import config, filemanager

log = logging.getLogger(__name__)

def _create_s3_object(file_path: Union[Path, str]) -> str:
    file_name = file_path.name if isinstance(file_path, Path) else file_path
    return f"{config.PROJECT_ID}/{config.NODE_UUID}/{file_name}"


async def _push_file(file_path: Path, rename_to: Optional[str]):
    store_id = 0 # this is for simcore.s3
    s3_object = _create_s3_object(file_path)
    log.info("uploading %s to S3 to %s...", file_path.name, s3_object)
    await filemanager.upload_file(store_id=store_id,
                                s3_object=s3_object,
                                local_file_path=file_path)
    log.info("%s successfuly uploaded", file_path)

async def push(file_or_folder: Path, rename_to: Optional[str] = None):
    if file_or_folder.is_file():
        return await _push_file(file_or_folder, rename_to)
    # we have a folder, so we create a compressed file
    with TemporaryDirectory() as tmp_dir_name:
        log.info("compressing %s into %s...", file_or_folder.name, tmp_dir_name)
        # compress the files
        compressed_file_wo_ext = Path(tmp_dir_name) / (rename_to if rename_to else file_or_folder.stem)
        archive_file = Path(make_archive(str(compressed_file_wo_ext), 'zip', root_dir=file_or_folder)) #, base_dir=folder))
        return await _push_file(archive_file, rename_to)

async def _pull_file(file_path: Path):
    s3_object = _create_s3_object(file_path)
    log.info("pulling data from %s to %s...", s3_object, file_path)
    downloaded_file = await filemanager.download_file(store_id=0, s3_object=s3_object, local_folder=file_path.parent)
    if downloaded_file != file_path:
        if file_path.exists():
            file_path.unlink()
        move(downloaded_file, file_path)
    log.info("%s successfuly pulled", file_path)

async def pull(file_or_folder: Path):
    if file_or_folder.is_file():
        return await _pull_file(file_or_folder)
    # we have a folder, so we need somewhere to extract it to
    with TemporaryDirectory() as tmp_dir_name:
        archive_file = Path(tmp_dir_name) / "{}.zip".format(file_or_folder.stem)
        await _pull_file(archive_file)
        log.info("extracting data from %s", archive_file)
        unpack_archive(str(archive_file), extract_dir=file_or_folder)
        log.info("extraction completed")
