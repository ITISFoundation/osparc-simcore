#!/usr/bin/python3

import cgi
import cgitb
import logging
from pathlib import Path

cgitb.enable()
print("Content-Type: text/html;charset=utf-8")
print()

form = cgi.FieldStorage()
server_port = form["port"].value
log = logging.getLogger(__name__)
_INPUT_FILE = Path(r"/home/root/trigger/server_port")

with _INPUT_FILE.open(mode='w') as fp:
    fp.write(str(server_port))
