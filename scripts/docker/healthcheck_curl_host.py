import os
import sys

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

print(0 if urlopen("{host}{baseurl}".format(host=sys.argv[1], baseurl=os.environ.get("SIMCORE_NODE_BASEPATH", "")) ).getcode() == 200 else 1)
