import logging
from pathlib import Path
import time

log = logging.getLogger(__name__)
_INPUT_FILE = Path(r"/home/root/trigger/server_port")

log.debug("looking for file %s", _INPUT_FILE)
# wait till the file exists
while not _INPUT_FILE.exists():
    time.sleep(2)

log.debug("File %s appeared", _INPUT_FILE)

with _INPUT_FILE.open() as fp:
    hostname_port = fp.readline()
hostname = str(hostname_port).split(":")[0]
port = str(hostname_port).split(":")[1]
log.debug("host and port are: %s:%s", hostname, port)

# output for shell
print("{hostname},{port}".format(hostname=hostname, port=port))
