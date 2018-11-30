""" Configuration of simcore_service_storage

The application can consume settings revealed at different
stages of the development workflow. This submodule gives access
to all of them.


Naming convention:

APP_*_KEY: is a key in app-storage
RQT_*_KEY: is a key in request-storage
RSP_*_KEY: is a key in response-storage

See https://docs.aiohttp.org/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""

import logging

from servicelib import application_keys

# IMPORTANT: lowest level module
#   I order to avoid cyclic dependences, please
#   DO NOT IMPORT ANYTHING from . (except for __version__)
from .__version__ import get_version_object


log = logging.getLogger(__name__)


## CONSTANTS--------------------
RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

## VERSION-----------------------------
service_version = get_version_object()

## CONFIGURATION FILES------------------
DEFAULT_CONFIG='docker-prod-config.yaml'


APP_CONFIG_KEY = application_keys.APP_CONFIG_KEY # app-storage-key for config object
RSC_CONFIG_DIR_KEY  = "data"  # resource folder

# DSM specific constants
SIMCORE_S3_ID    = 0
SIMCORE_S3_STR   = "simcore.s3"

DATCORE_ID      = 1
DATCORE_STR     = "datcore"


# RSC=resource
RSC_CONFIG_DIR_KEY  = "data"
RSC_CONFIG_SCHEMA_KEY = RSC_CONFIG_DIR_KEY + "/config-schema-v1.json"


# REST API ----------------------------
API_MAJOR_VERSION = service_version.major # NOTE: syncs with service key
API_VERSION_TAG = "v{:.0f}".format(API_MAJOR_VERSION)

APP_OPENAPI_SPECS_KEY = application_keys.APP_OPENAPI_SPECS_KEY # app-storage-key for openapi specs object


# DATABASE ----------------------------
APP_DB_ENGINE_KEY  = __name__ + '.db_engine'
APP_DB_SESSION_KEY = __name__ + '.db_session'


# DATA STORAGE MANAGER ----------------------------------
APP_DSM_THREADPOOL = __name__ + '.dsm_threadpool'
APP_DSM_KEY = __name__ + ".DSM"
APP_S3_KEY = __name__ + ".S3_CLIENT"
