#!/bin/python
""" Healthcheck script to run inside docker

Example of usage in a Dockerfile
```
    COPY --chown=scu:scu docker/healthcheck.py docker/healthcheck.py
    HEALTHCHECK --interval=30s \
                --timeout=30s \
                --start-period=1s \
                --retries=3 \
                CMD python3 docker/healthcheck.py http://localhost:8000/
```

Q&A:
    1. why not to use curl instead of a python script?
        - SEE https://blog.sixeyed.com/docker-healthchecks-why-not-to-use-curl-or-iwr/
"""

import os
import sys
from contextlib import suppress
from urllib.request import urlopen

# Disabled if boots with debugger (e.g. debug, pdb-debug, debug-ptvsd, etc)
SC_BOOT_MODE = os.environ.get("SC_BOOT_MODE", "")

# Adds a base-path if defined in environ
SIMCORE_NODE_BASEPATH = os.environ.get("SIMCORE_NODE_BASEPATH", "")


def is_service_healthy() -> bool:
    if "debug" in SC_BOOT_MODE.lower():
        return True

    with suppress(Exception):
        with urlopen(f"{sys.argv[1]}{SIMCORE_NODE_BASEPATH}") as f:
            return f.getcode() == 200
    return False


sys.exit(os.EX_OK if is_service_healthy() else os.EX_UNAVAILABLE)
