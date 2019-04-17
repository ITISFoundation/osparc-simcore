import logging
from tempfile import TemporaryDirectory
from pathlib import Path
from shutil import make_archive

from simcore_sdk.node_ports import filemanager, config

log = logging.getLogger(__name__)

async def push(folder: Path):
    folder = Path(folder)
    with TemporaryDirectory() as tmp_dir_name:
        log.info("compressing %s into %s...", folder.name, tmp_dir_name)
        # compress the files
        compressed_file_wo_ext = Path(tmp_dir_name) / folder.stem
        archive_file = Path(make_archive(compressed_file_wo_ext, 'zip', root_dir=folder, base_dir=folder))

        store_id = 0 # this is for simcore.s3
        s3_object = "{}/{}/{}".format(config.PROJECT_ID, config.NODE_UUID, archive_file.name)
        log.info("uploading %s to S3 to %s...", archive_file.name, s3_object)
        await filemanager.upload_file(store_id=store_id,
                                    s3_object=s3_object,
                                    local_file_path=archive_file)
        log.info("%s successfuly uploaded")
