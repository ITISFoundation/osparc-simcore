import logging
from pathlib import Path
from shutil import make_archive, unpack_archive
from tempfile import TemporaryDirectory

from simcore_sdk.node_ports import config, filemanager

log = logging.getLogger(__name__)

def _create_s3_object(file_path: Path) -> str:
    return "{}/{}/{}".format(config.PROJECT_ID, config.NODE_UUID, file_path.name)

async def push(folder: Path):
    folder = Path(folder)
    with TemporaryDirectory() as tmp_dir_name:
        log.info("compressing %s into %s...", folder.name, tmp_dir_name)
        # compress the files
        compressed_file_wo_ext = Path(tmp_dir_name) / folder.stem
        archive_file = Path(make_archive(str(compressed_file_wo_ext), 'zip', root_dir=folder)) #, base_dir=folder))

        store_id = 0 # this is for simcore.s3
        s3_object = _create_s3_object(archive_file)
        log.info("uploading %s to S3 to %s...", archive_file.name, s3_object)
        await filemanager.upload_file(store_id=store_id,
                                    s3_object=s3_object,
                                    local_file_path=archive_file)
        log.info("%s successfuly uploaded", folder)


async def pull(folder: Path):
    with TemporaryDirectory() as tmp_dir_name:
        archive_file = Path(tmp_dir_name) / "{}.zip".format(folder.stem)
        s3_object = _create_s3_object(archive_file)
        log.info("pulling data from %s to %s...", s3_object, archive_file)
        await filemanager.download_file(store_id=0, s3_object=s3_object, local_file_path=archive_file)
        log.info("extracting data from %s", archive_file)
        unpack_archive(str(archive_file), extract_dir=folder)
        log.info("extraction completed")
