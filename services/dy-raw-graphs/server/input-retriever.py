import asyncio
import json
import logging
import os
import shutil
import sys
import tarfile
import time
import zipfile
from pathlib import Path

from simcore_sdk import node_ports

logger = logging.getLogger(__name__)

_INPUT_PATH = Path(os.environ.get("RAWGRAPHS_INPUT_PATH"))

# clean the directory
shutil.rmtree(str(_INPUT_PATH), ignore_errors=True)

if not _INPUT_PATH.exists():
    _INPUT_PATH.mkdir()
    logger.debug("Created input folder at %s", _INPUT_PATH)

async def retrieve_data():
    logger.info("retrieving data from simcore...")
    print("retrieving data from simcore...")

    # get all files in the local system and copy them to the input folder
    start_time = time.time()
    PORTS = node_ports.ports()
    download_tasks = []
    for port in PORTS.inputs:
        if not port or port.value is None:
            continue
        
        # collect coroutines
        download_tasks.append(port.get())
    if download_tasks:
        downloaded_files = await asyncio.gather(*download_tasks)
        print("downloaded {} files /tmp <br>".format(len(download_tasks)))
        for local_path in downloaded_files:
            if local_path is None:
                continue
            # logger.debug("Completed download of %s in local path %s", port.value, local_path)
            if local_path.exists():
                if zipfile.is_zipfile(str(local_path)):
                    zip_ref = zipfile.ZipFile(str(local_path), 'r')
                    zip_ref.extractall(str(_INPUT_PATH))
                    zip_ref.close()
                    logger.debug("Unzipped")
                    print("unzipped {file} to {path}<br>".format(file=str(local_path), path=str(_INPUT_PATH)))
                else:
                    logger.debug("Start moving %s to input path %s", local_path, _INPUT_PATH)
                    shutil.move(str(local_path), str(_INPUT_PATH / local_path.name))
                    logger.debug("Move completed")
                    print("moved {file} to {path}<br>".format(file=str(local_path), path=str(_INPUT_PATH)))
            end_time = time.time()
        print("time to download: {} seconds".format(end_time - start_time))

async def retrieve_data2():
    logger.info("retrieving data from simcore...")
    print("retrieving data from simcore...")

    # get all files in the local system and copy them to the input folder
    PORTS = node_ports.ports()
    for port in PORTS.inputs:
        if not port or port.value is None:
            continue

        local_path = await port.get()
        dest_path = _INPUT_PATH / port.key
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
            dest_path_name = _INPUT_PATH / (port.key + ":" + Path(local_path).name)
            shutil.move(local_path, dest_path_name)
            shutil.rmtree(Path(local_path).parents[0])

# asyncio.get_event_loop().run_until_complete(retrieve_data())



_INPUTS_FOLDER = Path(os.environ.get("RAWGRAPHS_INPUT_PATH"))
_OUTPUTS_FOLDER = Path(os.environ.get("RAWGRAPHS_OUTPUT_PATH"))
_FILE_TYPE_PREFIX = "data:"
_KEY_VALUE_FILE_NAME = "key_values.json"

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
    PORTS = node_ports.ports()
    inputs_path = Path(_INPUTS_FOLDER).expanduser()
    values = {}
    for port in PORTS.inputs:
        if not port or port.value is None:
            continue
        logger.debug("downloading data from port '%s' with value '%s'...", port.key, port.value)
        value = await port.get()
        values[port.key] = {"key": port.key, "value": value}

        if _FILE_TYPE_PREFIX in port.type:
            dest_path = inputs_path / port.key
            dest_path.mkdir(exist_ok=True, parents=True)
            values[port.key] = {"key": port.key, "value": str(dest_path)}

            # clean up destination directory
            for path in dest_path.iterdir():
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            # check if value is a compressed file
            if tarfile.is_tarfile(value):
                with tarfile.open(value) as tar_file:
                    tar_file.extractall(dest_path, members=_no_relative_path_tar(tar_file))
            elif zipfile.is_zipfile(value):
                with zipfile.ZipFile(value) as zip_file:
                    zip_file.extractall(dest_path, members=_no_relative_path_zip(zip_file))
            else:
                dest_path = dest_path / Path(value).name
                shutil.move(value, dest_path)

    values_file = inputs_path / _KEY_VALUE_FILE_NAME
    values_file.write_text(json.dumps(values))
    logger.info("all data retrieved from simcore: %s", values)

async def upload_data():
    logger.info("uploading data to simcore...")
    PORTS = node_ports.ports()
    outputs_path = Path(_OUTPUTS_FOLDER).expanduser()
    for port in PORTS.outputs:
        logger.debug("uploading data to port '%s' with value '%s'...", port.key, port.value)
        if _FILE_TYPE_PREFIX in port.type:
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
        else:
            values_file = outputs_path / _KEY_VALUE_FILE_NAME
            if values_file.exists():
                values = json.loads(values_file.read_text())
                if port.key in values and values[port.key] is not None:
                    await port.set(values[port.key])

    logger.info("all data uploaded to simcore")

async def sync_data():
    try:
        # await download_data()
        await retrieve_data2()
        # await upload_data()
        # self.set_status(200)
    except node_ports.exceptions.NodeportsException as exc:
        # self.set_status(500, reason=str(exc))
        logger.error("error when syncing '%s'", str(exc))
        sys.exit(1)
    finally:
        # self.finish('completed retrieve!')
        logger.info("download and upload finished")

asyncio.get_event_loop().run_until_complete(sync_data())
