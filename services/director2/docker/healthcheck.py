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

SUCCESS, UNHEALTHY = 0, 1

# Disabled if boots with debugger (e.g. debug, pdb-debug, debug-ptvsd, etc)
ok = "debug" in os.environ.get("SC_BOOT_MODE").lower()

# Queries host
ok = (
    ok
    or urlopen(
        "{host}{baseurl}".format(
            host=sys.argv[1], baseurl=os.environ.get("SIMCORE_NODE_BASEPATH", "")
        )  # adds a base-path if defined in environ
    ).getcode()
    == 200
)


sys.exit(SUCCESS if ok else UNHEALTHY)
