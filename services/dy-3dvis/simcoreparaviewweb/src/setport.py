#!/usr/bin/python3

import cgitb
cgitb.enable()
print("Content-Type: text/html;charset=utf-8")
print()

import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)
_INPUT_FILE = Path(r"/home/root/trigger/server_port")

server_port = 23456

with _INPUT_FILE.open(mode='w') as fp:
    fp.write(str(server_port))