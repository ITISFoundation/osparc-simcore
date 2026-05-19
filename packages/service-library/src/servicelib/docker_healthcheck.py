#!/bin/python
"""Healthcheck script to run inside docker containers.

Example of usage in a Dockerfile:
```
    HEALTHCHECK --interval=30s \
                --timeout=30s \
                --start-period=20s \
                --start-interval=1s \
                --retries=3 \
                CMD ["python3", "-m", "servicelib.docker_healthcheck", "http://localhost:8080/v0/"]
```

Alternative script invocation (same module):
```
    CMD ["python3", "-c", "from servicelib.docker_healthcheck import main; raise SystemExit(main())", "http://localhost:8080/v0/"]
```

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

# Adds a base-path if defined in environ
SIMCORE_NODE_BASEPATH = os.environ.get("SIMCORE_NODE_BASEPATH", "")
HTTP_STATUS_OK = 200
MIN_REQUIRED_ARGS = 2


def is_service_healthy() -> bool:
    if "debug" in SC_BOOT_MODE.lower():
        return True

    with suppress(Exception), urlopen(f"{sys.argv[1]}{SIMCORE_NODE_BASEPATH}") as f:  # noqa: S310
        return bool(f.getcode() == HTTP_STATUS_OK)
    return False


def main() -> int:
    if len(sys.argv) < MIN_REQUIRED_ARGS:
        return os.EX_USAGE
    return os.EX_OK if is_service_healthy() else os.EX_UNAVAILABLE


if __name__ == "__main__":
    sys.exit(main())
