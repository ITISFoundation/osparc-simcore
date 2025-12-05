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
from urllib.request import urlopen

from celery_library.worker.heartbeat import is_healthy
from simcore_service_notifications.core.application import ApplicationSettings

SUCCESS, UNHEALTHY = 0, 1

# Disabled if boots with debugger
is_debug = os.getenv("SC_BOOT_MODE", "").lower() == "debug"

# Queries host
# pylint: disable=consider-using-with


def is_service_healthy() -> bool:
    settings = ApplicationSettings.create_from_envs()

    if settings.NOTIFICATIONS_WORKER_MODE:
        print("Healthcheck: checking celery worker health")
        return is_healthy()

    print("Healthcheck: checking HTTP service health")
    code = urlopen(
        "{host}{baseurl}".format(
            host=sys.argv[1], baseurl=os.environ.get("SIMCORE_NODE_BASEPATH", "")
        )  # adds a base-path if defined in environ
    ).getcode()
    print(f"Healthcheck: HTTP status code={code}")
    return code == 200


sys.exit(SUCCESS if is_debug or is_service_healthy() else UNHEALTHY)
