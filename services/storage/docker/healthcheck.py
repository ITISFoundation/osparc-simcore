#!/bin/python
# pylint: disable=consider-using-with

""" Healthcheck script to run inside docker

Example of usage in a Dockerfile
```
    COPY --chown=scu:scu docker/healthcheck.py docker/healthcheck.py
    HEALTHCHECK --interval=30s \
                --timeout=30s \
                --start-period=1s \
                --retries=3 \
                CMD python3 docker/healthcheck.py http://localhost:8080/v0/
```

Q&A:
    1. why not to use curl instead of a python script?
        - SEE https://blog.sixeyed.com/docker-healthchecks-why-not-to-use-curl-or-iwr/
"""


import os
import subprocess
import sys
from urllib.request import urlopen

from simcore_service_storage.main import ApplicationSettings

SUCCESS, UNHEALTHY = 0, 1

# Disabled if boots with debugger
ok = os.getenv("SC_BOOT_MODE", "").lower() == "debug"

# Queries host
# pylint: disable=consider-using-with
app_settings = ApplicationSettings.create_from_envs()

broker_url = app_settings.STORAGE_CELERY.CELERY_BROKER.dsn


def _is_celery_worker_healthy():
    try:
        result = subprocess.run(
            [
                "celery",
                "-b",
                broker_url,
                "inspect",
                "ping",
                "-d",
                "celery@" + os.getenv("HOSTNAME", ""),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return "pong" in result.stdout
    except subprocess.CalledProcessError:
        return False


print(_is_celery_worker_healthy())

ok = (
    ok
    or (bool(os.getenv("STORAGE_WORKER_MODE", "") and _is_celery_worker_healthy()))
    or urlopen(
        "{host}{baseurl}".format(
            host=sys.argv[1], baseurl=os.environ.get("SIMCORE_NODE_BASEPATH", "")
        )  # adds a base-path if defined in environ
    ).getcode()
    == 200
)

sys.exit(SUCCESS if ok else UNHEALTHY)
