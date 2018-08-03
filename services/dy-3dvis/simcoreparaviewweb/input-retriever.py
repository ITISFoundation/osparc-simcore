#!/usr/bin/python3

import cgitb
cgitb.enable()

import logging
import os
import shutil
import sys
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

print("Content-Type: text/html;charset=utf-8")
print()

from simcore_sdk.nodeports.nodeports import PORTS

INPUT_PATH = Path(os.environ.get("PARAVIEW_INPUT_PATH"))
if not INPUT_PATH.exists():    
    INPUT_PATH.mkdir()
    _LOGGER.debug("Created input folder at %s", INPUT_PATH)
# get all files in the local system and copy them to the input folder
for node_input in PORTS.inputs:
    if node_input.type in ("file-url", "folder-url"):
        _LOGGER.debug("Start downloading path %s", node_input.value)
        local_path = Path(node_input.get())
        _LOGGER.debug("Completed download of %s in local path %s", node_input.value, local_path)
        if local_path.exists():
            file_name = local_path.name
            _LOGGER.debug("Start moving %s to input path %s", local_path, INPUT_PATH)
            print("-----------------")
            print("Start moving {} to input path {}/{}".format(local_path, INPUT_PATH, file_name))
            shutil.move(str(local_path), str(INPUT_PATH / file_name))
            _LOGGER.debug("Move completed")
            print("Move completed")
