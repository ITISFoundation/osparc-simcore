from servicelib.aiohttp import application_keys

from . import _meta

RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

## VERSION-----------------------------
service_version = _meta.version

## CONFIGURATION FILES------------------
DEFAULT_CONFIG = "docker-prod-config.yaml"


APP_CONFIG_KEY = application_keys.APP_CONFIG_KEY  # app-storage-key for config object
RSC_CONFIG_DIR_KEY = "data"  # resource folder

# DSM specific constants
SIMCORE_S3_ID = 0
SIMCORE_S3_STR = "simcore.s3"

DATCORE_ID = 1
DATCORE_STR = "datcore"


# REST API ----------------------------
API_MAJOR_VERSION = service_version.major  # NOTE: syncs with service key
API_VERSION_TAG = "v{:.0f}".format(API_MAJOR_VERSION)

APP_OPENAPI_SPECS_KEY = (
    application_keys.APP_OPENAPI_SPECS_KEY
)  # app-storage-key for openapi specs object


# DATABASE ----------------------------
APP_DB_ENGINE_KEY = f"{__name__}.db_engine"


# DATA STORAGE MANAGER ----------------------------------
APP_DSM_THREADPOOL = f"{__name__}.dsm_threadpool"
APP_DSM_KEY = f"{__name__}.DSM"
APP_S3_KEY = f"{__name__}.S3_CLIENT"
