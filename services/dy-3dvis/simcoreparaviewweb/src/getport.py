import logging
from pathlib import Path
import time

_LOGGER = logging.getLogger(__name__)
_INPUT_FILE = Path(r"/home/root/trigger/server_port")

_LOGGER.debug("looking for file %s", _INPUT_FILE)
# wait till the file exists
while not _INPUT_FILE.exists():
    time.sleep(2)    

_LOGGER.debug("File %s appeared", _INPUT_FILE)

with _INPUT_FILE.open() as fp:
    server_port = fp.readline()
_LOGGER.debug("server port is: %s", server_port)

# output for shell
print(server_port)