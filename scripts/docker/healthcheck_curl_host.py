import os
import sys

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

BOOTS_WITH_DEBUGGER = "2"
if os.environ.get("DEBUG") == BOOTS_WITH_DEBUGGER:
    # Healthcheck disabled with service is boot with a debugger
    print(0)
else:
    print(0 if urlopen("{host}{baseurl}".format(
        host=sys.argv[1],
        baseurl=os.environ.get("SIMCORE_NODE_BASEPATH", ""))
        ).getcode() == 200
        else 1)
