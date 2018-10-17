""" Configuration keys for simcore_service_webserver

The application can consume settings revealed at different
stages of its lifetime workflow:
    - from development/statics : e.g. constants, api-specs,...
    - at build-time: e.g. versioning,
    - on startup: use configuration file (accounts for environment variables) and command-line

TODO: this should be the actual settings
"""
import logging

import servicelib.storage_keys

from ..__version__ import get_version_object

log = logging.getLogger(__name__)


## CONSTANTS-----------------------------
TIMEOUT_IN_SECS = 2

## VERSIONS -----------------------------
package_version = get_version_object()

API_MAJOR_VERSION = package_version.major
API_URL_VERSION = "v{:.0f}".format(API_MAJOR_VERSION)


# STORAGE KEYS -------------------------

# APP=application
APP_CONFIG_KEY = servicelib.storage_keys.APP_CONFIG_KEY
APP_OPENAPI_SPECS_KEY = servicelib.storage_keys.APP_OPENAPI_SPECS_KEY

# CFG=configuration

# RSC=resource
RSC_CONFIG_KEY  = "config"
RSC_OPENAPI_KEY = "oas3/{}/openapi.yaml".format(API_URL_VERSION)

# RQT=request


# RSP=response


## Settings revealed at runtime: only known when the application starts
#  - via the config file passed to the cli
