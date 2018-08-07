#!/usr/bin/python3

import cgitb
cgitb.enable()

import logging
import os
import shutil
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

print("Content-Type: text/html;charset=utf-8")
print()

print(os.environ)

from simcore_sdk.nodeports.nodeports import PORTS

_INPUT_PATH = Path(os.environ.get("PARAVIEW_INPUT_PATH"))
if not _INPUT_PATH.exists():    
    _INPUT_PATH.mkdir()
    _LOGGER.debug("Created input folder at %s", _INPUT_PATH)
# get all files in the local system and copy them to the input folder
for node_input in PORTS.inputs:
    if node_input.type in ("file-url", "folder-url"):
        _LOGGER.debug("Start downloading path %s", node_input.value)
        local_path = Path(node_input.get())
        _LOGGER.debug("Completed download of %s in local path %s", node_input.value, local_path)
        if local_path.exists():
            file_name = local_path.name
            _LOGGER.debug("Start moving %s to input path %s", local_path, _INPUT_PATH)
            shutil.move(str(local_path), str(_INPUT_PATH / file_name) + ".vtk")
            _LOGGER.debug("Move completed")
            print("Move completed")
