""" Configuration of simcore_service_storage

The application can consume settings revealed at different
stages of the development workflow. This submodule gives access
to all of them.

"""
import logging

import trafaret as T

from simcore_sdk.config import db, s3

from .__version__ import get_version_object

log = logging.getLogger(__name__)

## Constants: low-level tweaks ------------------------------

TIMEOUT_IN_SECS = 2

DEFAULT_CONFIG='config-prod.yaml'
CONFIG_KEY="config"

## Config file schema
# FIXME: load from json schema instead!
_APP_SCHEMA = T.Dict({
    "host": T.IP,
    "port": T.Int(),
    "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL", "NOTSET"),
    "testing": T.Bool(),
    T.Key("disable_services", default=[], optional=True): T.List(T.String())
})

CONFIG_SCHEMA = T.Dict({
    "version": T.String(),
    T.Key("main"): _APP_SCHEMA,
    T.Key("postgres"): db.CONFIG_SCHEMA,
    T.Key("s3"): s3.CONFIG_SCHEMA
})


## BUILD ------------------------
#  - Settings revealed at build/installation time
#  - Only known after some setup or build step is completed
PACKAGE_VERSION = get_version_object()

API_MAJOR_VERSION = PACKAGE_VERSION.major
API_URL_VERSION = "v{:.0f}".format(API_MAJOR_VERSION)

RESOURCE_KEY_OPENAPI = "oas3/{}".format(API_URL_VERSION)
OAS_ROOT_FILE = "{}/openapi.yaml".format(RESOURCE_KEY_OPENAPI)



## Settings revealed at runtime: only known when the application starts
#  - via the config file passed to the cli
