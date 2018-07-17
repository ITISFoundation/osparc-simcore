from simcore_sdk.nodeports.nodeports import PORTS
import pathlib
import shutil
import logging

_LOGGER = logging.getLogger(__name__)

INPUT_PATH = pathlib.Path("/home/scu/inputs")

# get all files in the local system and copy them to the input folder
for node_input in PORTS.inputs:
    if node_input.type != "file-url":
        continue
        
    local_file_path = pathlib.Path(node_input.get())
    if local_file_path.exists():
        file_name = local_file_path.name
        shutil.copy(local_file_path, INPUT_PATH / file_name)