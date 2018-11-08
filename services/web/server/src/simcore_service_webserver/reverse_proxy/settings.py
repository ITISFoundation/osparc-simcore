""" subsystem settings - list of named settings

"""

SERVICE_ID_KEY = "serviceId"
PROXY_PATH_KEY = "proxyPath"

# NOTE: All dynamic backend services should have this basepath as mount point
#       due to a limitation of proxied services!!!!

PROXY_MOUNTPOINT = r"/x"
BACKEND_MOUNTPOINT = r"/{%s}" % SERVICE_ID_KEY

# /x/{serviceId}/{proxyPath:.*}
URL_PATH = PROXY_MOUNTPOINT + BACKEND_MOUNTPOINT + r"/{%s:.*}" % PROXY_PATH_KEY
