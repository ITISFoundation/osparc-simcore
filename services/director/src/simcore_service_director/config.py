"""Director service configuration
"""

import logging
import os

from servicelib.client_session import APP_CLIENT_SESSION_KEY

DEBUG_MODE = os.environ.get("DEBUG", False) in ["true", "True", True]

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

API_VERSION = "v0"
API_ROOT = "oas3"

REGISTRY_CACHING = os.environ.get("REGISTRY_CACHING", True) in ["true", "True", True]
REGISTRY_CACHING_TTL = os.environ.get("REGISTRY_CACHING_TTL", 15*60)
APP_REGISTRY_CACHE_DATA_KEY = __name__ + "_registry_cache_data"

REGISTRY_AUTH = os.environ.get("REGISTRY_AUTH", False) in ["true", "True", True]
REGISTRY_USER = os.environ.get("REGISTRY_USER", "")
REGISTRY_PW = os.environ.get("REGISTRY_PW", "")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "")
REGISTRY_SSL = os.environ.get("REGISTRY_SSL", True) in ["true", "True", True]

EXTRA_HOSTS_SUFFIX = os.environ.get("EXTRA_HOSTS_SUFFIX", "undefined")

# these are the envs passed to the dynamic services by default
SERVICES_DEFAULT_ENVS = {
    "POSTGRES_ENDPOINT": os.environ.get("POSTGRES_ENDPOINT", "undefined postgres endpoint"),
    "POSTGRES_USER": os.environ.get("POSTGRES_USER", "undefined postgres user"),
    "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", "undefined postgres password"),
    "POSTGRES_DB": os.environ.get("POSTGRES_DB", "undefined postgres db"),
    "STORAGE_ENDPOINT": os.environ.get("STORAGE_ENDPOINT", "undefined storage endpoint")
}

# some services need to know the published host to be functional (paraview)
# TODO: please review if needed
PUBLISHED_HOST_NAME = os.environ.get("PUBLISHED_HOST_NAME", "")
# used when in devel mode vs release mode
NODE_SCHEMA_LOCATION = os.environ.get("NODE_SCHEMA_LOCATION",
    "{root}/{version}/schemas/node-meta-v0.0.1.json".format(root=API_ROOT, version=API_VERSION))
# used to find the right network name
SIMCORE_SERVICES_NETWORK_NAME = os.environ.get("SIMCORE_SERVICES_NETWORK_NAME")
# useful when developing with an alternative registry namespace
SIMCORE_SERVICES_PREFIX = os.environ.get("SIMCORE_SERVICES_PREFIX", "simcore/services")

# tracing
TRACING_ENABLED = os.environ.get("TRACING_ENABLED", True) in ["true", "True", True]
TRACING_ZIPKIN_ENDPOINT = os.environ.get("TRACING_ZIPKIN_ENDPOINT", "http://jaeger:9411")

__all__ = [
    'APP_CLIENT_SESSION_KEY'
]
