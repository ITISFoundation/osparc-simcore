#!/bin/python
"""Healthcheck script to run inside docker containers.

This script is designed to be **standalone** — it only uses the Python standard
library so that it can be invoked with ``python3 -S`` (skipping site-packages)
for near-instant startup even in containers with hundreds of installed packages.

Recommended usage in a Dockerfile (fast — skips site-packages scanning):
```
    COPY --chown=scu:scu \
        packages/common-library/src/common_library/docker_healthcheck.py \
        docker/healthcheck.py

    HEALTHCHECK --interval=30s \
                --timeout=30s \
                --start-period=20s \
                --start-interval=1s \
                --retries=3 \
                CMD ["python3", "-S", "docker/healthcheck.py", "http://localhost:8080/v0/"]
```

Legacy usage (still works but slow due to full Python startup):
```
    HEALTHCHECK CMD ["python3", "-m", "common_library.docker_healthcheck", "http://localhost:8080/v0/"]
```

Worker-mode (heartbeat) usage:
    When a container runs as a Celery worker (no HTTP server), set
    ``HEALTHCHECK_MODE=heartbeat`` in the environment. The script will
    check a heartbeat file (written by ``common_library.heartbeat.update_heartbeat()``)
    instead of making an HTTP request.

Q&A:
    1. why not to use curl instead of a python script?
        - SEE https://blog.sixeyed.com/docker-healthchecks-why-not-to-use-curl-or-iwr/
"""

import os
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Final
from urllib.request import urlopen

# Disabled if boots with debugger (e.g. debug, pdb-debug, debug-ptvsd, debugpy, etc)
SC_BOOT_MODE: Final = os.environ.get("SC_BOOT_MODE", "")

# Adds a base-path if defined in environ
SIMCORE_NODE_BASEPATH: Final = os.environ.get("SIMCORE_NODE_BASEPATH", "")

# When set to "heartbeat", uses file-based heartbeat instead of HTTP
HEALTHCHECK_MODE: Final = os.environ.get("HEALTHCHECK_MODE", "")

HTTP_STATUS_OK: Final = 200
MIN_REQUIRED_ARGS: Final = 2

_HEARTBEAT_FILE: Final[Path] = Path(tempfile.gettempdir()) / "heartbeat"
_HEARTBEAT_THRESHOLD_SECONDS: Final = 10


def _is_heartbeat_healthy() -> bool:
    try:
        heartbeat = float(_HEARTBEAT_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return (time.time() - heartbeat) <= _HEARTBEAT_THRESHOLD_SECONDS


def is_service_healthy() -> bool:
    if "debug" in SC_BOOT_MODE.lower():
        return True

    if HEALTHCHECK_MODE == "heartbeat":
        return _is_heartbeat_healthy()

    with suppress(Exception), urlopen(f"{sys.argv[1]}{SIMCORE_NODE_BASEPATH}") as f:  # noqa: S310
        return bool(f.getcode() == HTTP_STATUS_OK)
    return False


def main() -> int:
    if HEALTHCHECK_MODE != "heartbeat" and len(sys.argv) < MIN_REQUIRED_ARGS:
        return os.EX_USAGE
    return os.EX_OK if is_service_healthy() else os.EX_UNAVAILABLE


if __name__ == "__main__":
    sys.exit(main())
