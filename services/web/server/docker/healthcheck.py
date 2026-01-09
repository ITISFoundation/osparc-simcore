#!/bin/python
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
import sys
from urllib.request import urlopen

SUCCESS, UNHEALTHY = 0, 1
HTTP_OK = 200
# Disabled if boots with debugger
ok = os.environ.get("SC_BOOT_MODE", "").lower() == "debug"

# Queries host
# pylint: disable=consider-using-with
ok = (
    ok
    or urlopen(  # noqa: S310
        "{host}{baseurl}".format(
            host=sys.argv[1], baseurl=os.environ.get("SIMCORE_NODE_BASEPATH", "")
        )  # adds a base-path if defined in environ
    ).getcode()
    == HTTP_OK
)

sys.exit(SUCCESS if ok else UNHEALTHY)
