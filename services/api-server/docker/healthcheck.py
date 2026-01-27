#!/bin/python
""" Healthcheck script to run inside docker

Example of usage in a Dockerfile
```
    COPY --chown=scu:scu docker/healthcheck.py docker/healthcheck.py
    HEALTHCHECK --interval=30s \
                --timeout=30s \
                --start-period=20s \
                --start-interval=1s \
                --retries=3 \
                CMD python3 docker/healthcheck.py http://localhost:8080/v0/
```

Q&A:
    1. why not to use curl instead of a python script?
        - SEE https://blog.sixeyed.com/docker-healthchecks-why-not-to-use-curl-or-iwr/
"""

import os
import sys
from urllib.request import urlopen

from celery_library.worker.heartbeat import is_healthy
from pydantic import TypeAdapter

SUCCESS, UNHEALTHY = 0, 1

# Disabled if boots with debugger
is_debug_mode = os.environ.get("SC_BOOT_MODE", "").lower() == "debug"


def is_service_healthy() -> bool:
    worker_mode = TypeAdapter(bool).validate_python(os.getenv("API_SERVER_WORKER_MODE", "False"))
    if worker_mode:
        return is_healthy()

    return (
        # Queries host
        urlopen(
            "{host}{baseurl}".format(
                host=sys.argv[1], baseurl=os.getenv("SIMCORE_NODE_BASEPATH", "")
            )  # adds a base-path if defined in environ
        ).getcode()
        == 200
    )


sys.exit(SUCCESS if is_debug_mode or is_service_healthy() else UNHEALTHY)
