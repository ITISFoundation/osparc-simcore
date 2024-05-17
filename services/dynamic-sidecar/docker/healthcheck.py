#!/bin/python
""" Healthcheck script to run inside docker

Q&A:
    1. why not to use curl instead of a python script?
        - SEE https://blog.sixeyed.com/docker-healthchecks-why-not-to-use-curl-or-iwr/
"""

import os
import sys
from contextlib import suppress
from urllib.request import urlopen

# Disabled if boots with debugger (e.g. debug, pdb-debug, debug-ptvsd, debugpy, etc)
SC_BOOT_MODE = os.environ.get("SC_BOOT_MODE", "")


def is_service_healthy() -> bool:
    if "debug" in SC_BOOT_MODE.lower():
        return True

    with suppress(Exception), urlopen(sys.argv[1]) as f:
        return f.getcode() == 200
    return False


sys.exit(os.EX_OK if is_service_healthy() else os.EX_UNAVAILABLE)
