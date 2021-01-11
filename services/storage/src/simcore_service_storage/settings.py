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
from typing import Any, Dict, List, Optional

from models_library.basic_types import LogLevel
from models_library.settings.application_bases import BaseAiohttpAppSettings
from models_library.settings.postgres import PostgresSettings
from models_library.settings.s3 import S3Config
from pydantic import BaseSettings, Field, SecretStr
from servicelib import application_keys
from servicelib.tracing import TracingSettings

from .meta import version

log = logging.getLogger(__name__)


## CONSTANTS--------------------
RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

## VERSION-----------------------------
service_version = version

## CONFIGURATION FILES------------------
DEFAULT_CONFIG = "docker-prod-config.yaml"


APP_CONFIG_KEY = application_keys.APP_CONFIG_KEY  # app-storage-key for config object
RSC_CONFIG_DIR_KEY = "data"  # resource folder

# DSM specific constants
SIMCORE_S3_ID = 0
SIMCORE_S3_STR = "simcore.s3"

DATCORE_ID = 1
DATCORE_STR = "datcore"


# RSC=resource
RSC_CONFIG_DIR_KEY = "data"
RSC_CONFIG_SCHEMA_KEY = RSC_CONFIG_DIR_KEY + "/config-schema-v1.json"


# REST API ----------------------------
API_MAJOR_VERSION = service_version.major  # NOTE: syncs with service key
API_VERSION_TAG = "v{:.0f}".format(API_MAJOR_VERSION)

APP_OPENAPI_SPECS_KEY = (
    application_keys.APP_OPENAPI_SPECS_KEY
)  # app-storage-key for openapi specs object


# DATABASE ----------------------------
APP_DB_ENGINE_KEY = __name__ + ".db_engine"


# DATA STORAGE MANAGER ----------------------------------
APP_DSM_THREADPOOL = __name__ + ".dsm_threadpool"
APP_DSM_KEY = __name__ + ".DSM"
APP_S3_KEY = __name__ + ".S3_CLIENT"


class BfApiToken(BaseSettings):
    token_key: str = Field(..., env="BF_API_KEY")
    token_secret: str = Field(..., env="BF_API_SECRET")


class ApplicationSettings(BaseAiohttpAppSettings):
    loglevel: LogLevel = Field(
        "INFO", env=["STORAGE_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    testing: bool = False

    max_workers: int = 8

    monitoring_enabled: bool = False

    test_datcore: Optional[BfApiToken] = None

    disable_services: List[str] = []

    # settings for sub-modules
    postgres: PostgresSettings
    s3: S3Config
    rest: Dict[str, Any] = {"enabled": True}
    tracing: TracingSettings

    class Config:
        case_sensitive = False
        env_prefix = "STORAGE_"
        json_encoders = {SecretStr: lambda v: v.get_secret_value()}

    @classmethod
    def create_from_environ(cls):
        return cls(
            postgres=PostgresSettings(), s3=S3Config(), tracing=TracingSettings()
        )
