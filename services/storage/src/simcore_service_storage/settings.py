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

## Constants: low-level tweals ...
TIMEOUT_IN_SECS = 2
RESOURCE_KEY_OPENAPI = "oas3/v0"
DEFAULT_CONFIG='config-prod.yaml'
CONFIG_KEY="config"

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

## Settings revealed at build/installation time: only known after some setup or build step is completed
PACKAGE_VERSION = get_version_object()


## Settings revealed at runtime: only known when the application starts
#  - via the config file passed to the cli
