#!/usr/bin/python3

import cgi
import cgitb
import logging
from pathlib import Path

cgitb.enable()
print("Content-Type: text/html;charset=utf-8")
print()

form = cgi.FieldStorage()
server_hostname = form["hostname"].value
server_port = form["port"].value
log = logging.getLogger(__name__)
_INPUT_FILE = Path(r"/home/root/trigger/server_port")

with _INPUT_FILE.open(mode='w') as fp:
    fp.write("{hostname}:{port}".format(hostname=server_hostname, port=server_port))
