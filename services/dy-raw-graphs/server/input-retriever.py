import asyncio
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

from simcore_sdk import node_ports

logger = logging.getLogger(__name__)

_INPUTS_FOLDER = Path(os.environ.get("RAWGRAPHS_INPUT_PATH"))
_OUTPUTS_FOLDER = Path(os.environ.get("RAWGRAPHS_OUTPUT_PATH"))
_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

# clean the directory
shutil.rmtree(str(_INPUTS_FOLDER), ignore_errors=True)

if not _INPUTS_FOLDER.exists():
    _INPUTS_FOLDER.mkdir()
    logger.debug("Created input folder at %s", _INPUTS_FOLDER)

if not _OUTPUTS_FOLDER.exists():
    _OUTPUTS_FOLDER.mkdir()
    logger.debug("Created output folder at %s", _OUTPUTS_FOLDER)

def _no_relative_path_tar(members: tarfile.TarFile):
    for tarinfo in members:
        path = Path(tarinfo.name)
        if path.is_absolute():
            # absolute path are not allowed
            continue
        if path.match("/../"):
            # relative paths are not allowed
            continue
        yield tarinfo

def _no_relative_path_zip(members: zipfile.ZipFile):
    for zipinfo in members.infolist():
        path = Path(zipinfo.filename)
        if path.is_absolute():
            # absolute path are not allowed
            continue
        if path.match("/../"):
            # relative paths are not allowed
            continue
        yield zipinfo

async def download_data():
    logger.info("retrieving data from simcore...")
    print("retrieving data from simcore...")

    # get all files in the local system and copy them to the input folder
    PORTS = node_ports.ports()
    for port in PORTS.inputs:
        if not port or port.value is None:
            continue

        local_path = await port.get()
        dest_path = _INPUTS_FOLDER / port.key
        dest_path.mkdir(exist_ok=True, parents=True)

        # clean up destination directory
        for path in dest_path.iterdir():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        # check if local_path is a compressed file
        if tarfile.is_tarfile(local_path):
            with tarfile.open(local_path) as tar_file:
                tar_file.extractall(dest_path, members=_no_relative_path_tar(tar_file))
        elif zipfile.is_zipfile(local_path):
            with zipfile.ZipFile(local_path) as zip_file:
                zip_file.extractall(dest_path, members=_no_relative_path_zip(zip_file))
        else:
            dest_path_name = _INPUTS_FOLDER / (port.key + ":" + Path(local_path).name)
            shutil.move(local_path, dest_path_name)
            shutil.rmtree(Path(local_path).parents[0])

async def upload_data():
    logger.info("uploading data to simcore...")
    PORTS = node_ports.ports()
    outputs_path = Path(_OUTPUTS_FOLDER).expanduser()
    for port in PORTS.outputs:
        logger.debug("uploading data to port '%s' with value '%s'...", port.key, port.value)
        src_folder = outputs_path / port.key
        list_files = list(src_folder.glob("*"))
        if len(list_files) == 1:
            # special case, direct upload
            await port.set(list_files[0])
            continue
        # generic case let's create an archive
        if len(list_files) > 1:
            temp_file = tempfile.NamedTemporaryFile(suffix=".tgz")
            temp_file.close()
            for _file in list_files:
                with tarfile.open(temp_file.name, mode='w:gz') as tar_ptr:
                    for file_path in list_files:
                        tar_ptr.add(file_path, arcname=file_path.name, recursive=False)
            try:
                await port.set(temp_file.name)
            finally:
                #clean up
                Path(temp_file.name).unlink()

    logger.info("all data uploaded to simcore")

async def sync_data():
    try:
        await download_data()
        await upload_data()
        # self.set_status(200)
    except node_ports.exceptions.NodeportsException as exc:
        # self.set_status(500, reason=str(exc))
        logger.error("error when syncing '%s'", str(exc))
        sys.exit(1)
    finally:
        # self.finish('completed retrieve!')
        logger.info("download and upload finished")

asyncio.get_event_loop().run_until_complete(sync_data())
