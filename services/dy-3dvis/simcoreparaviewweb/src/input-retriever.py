#!/usr/bin/python3

import cgitb
cgitb.enable()

import logging
import os
import shutil
from pathlib import Path

import zipfile

log = logging.getLogger(__name__)

# necessary for CGI scripting compatiblity
# https://docs.python.org/3/library/cgi.html
print("Content-Type: text/html;charset=utf-8")
print()


from simcore_sdk.nodeports.nodeports import PORTS

_INPUT_PATH = Path(os.environ.get("PARAVIEW_INPUT_PATH"))

if not _INPUT_PATH.exists():
    _INPUT_PATH.mkdir()
    log.debug("Created input folder at %s", _INPUT_PATH)
# get all files in the local system and copy them to the input folder
for node_input in PORTS.inputs:
    if node_input.type in ("file-url", "folder-url"):
        log.debug("Start downloading path %s", node_input.value)
        local_path = Path(node_input.get())
        log.debug("Completed download of %s in local path %s", node_input.value, local_path)
        if local_path.exists():
            if zipfile.is_zipfile(str(local_path)):
                zip_ref = zipfile.ZipFile(str(local_path), 'r')
                zip_ref.extractall(str(_INPUT_PATH))
                zip_ref.close()
                log.debug("Unzipped")
                print("unzipped {file} in {path}\n".format(file=str(local_path), path=str(_INPUT_PATH)))
            else:
                log.debug("Start moving %s to input path %s", local_path, _INPUT_PATH)
                shutil.move(str(local_path), str(_INPUT_PATH / local_path.name) + ".vtk")
                log.debug("Move completed")
                print("moved {file} in {path}\n".format(file=str(local_path), path=str(_INPUT_PATH)))
