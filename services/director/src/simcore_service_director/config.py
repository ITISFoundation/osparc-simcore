"""Director service configuration
"""

import logging
import os

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

API_VERSION = "v0"

REGISTRY_AUTH = os.environ.get("REGISTRY_AUTH", False) in ["true", "True"]
REGISTRY_USER = os.environ.get("REGISTRY_USER", "")
REGISTRY_PW = os.environ.get("REGISTRY_PW", "")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "")
REGISTRY_SSL = os.environ.get("REGISTRY_SSL", True)
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
PUBLISHED_HOST_NAME = os.environ.get("PUBLISHED_HOST_NAME", "")
