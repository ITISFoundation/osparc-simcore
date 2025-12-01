#!/bin/python
""" Healthcheck script to run inside docker

Example of usage in a Dockerfile
```
    COPY --chown=scu:scu docker/healthcheck.py docker/healthcheck.py
    HEALTHCHECK --interval=10s \
                --timeout=5s \
                --start-period=60s \
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
ok = os.getenv("SC_BOOT_MODE", "").lower() == "debug"

# Queries host
# pylint: disable=consider-using-with

app_settings = ApplicationSettings.create_from_envs()


ok = (
    ok
    or (app_settings.NOTIFICATIONS_WORKER_MODE and is_healthy())
    or urlopen(
        "{host}{baseurl}".format(
            host=sys.argv[1], baseurl=os.environ.get("SIMCORE_NODE_BASEPATH", "")
        )  # adds a base-path if defined in environ
    ).getcode()
    == 200
)


sys.exit(SUCCESS if ok else UNHEALTHY)
