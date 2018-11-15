#!/usr/bin/python3

import cgitb
cgitb.enable()

import logging
import os
import shutil
from pathlib import Path

import zipfile

from simcore_sdk import node_ports

log = logging.getLogger(__name__)

# necessary for CGI scripting compatiblity
# https://docs.python.org/3/library/cgi.html
print("Content-Type: text/html;charset=utf-8")
print()


_INPUT_PATH = Path(os.environ.get("PARAVIEW_INPUT_PATH"))

# clean the directory
shutil.rmtree(str(_INPUT_PATH), ignore_errors=True)

if not _INPUT_PATH.exists():
    _INPUT_PATH.mkdir()
    log.debug("Created input folder at %s", _INPUT_PATH)

# get all files in the local system and copy them to the input folder
PORTS = node_ports.ports()
for node_input in PORTS.inputs:
    if not node_input or node_input.value is None:
        continue
    
    log.debug("Start downloading path %s", node_input.value)
    local_path = node_input.get()
    if local_path is None:
        continue
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
            shutil.move(str(local_path), str(_INPUT_PATH / local_path.name))
            log.debug("Move completed")
            print("moved {file} in {path}\n".format(file=str(local_path), path=str(_INPUT_PATH)))
