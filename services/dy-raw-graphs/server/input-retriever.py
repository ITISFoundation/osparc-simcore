import asyncio

import logging
import os
import shutil
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

asyncio.get_event_loop().run_until_complete(retrieve_data())
