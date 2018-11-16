""" Configuration of simcore_service_storage

The application can consume settings revealed at different
stages of the development workflow. This submodule gives access
to all of them.

"""
import logging

from servicelib import application_keys

from .__version__ import get_version_object
from .settings_schema import CONFIG_SCHEMA  # pylint: disable=W0611

log = logging.getLogger(__name__)

## CONSTANTS--------------------
TIMEOUT_IN_SECS = 2
RESOURCE_KEY_OPENAPI = "oas3/v0"


DEFAULT_CONFIG='docker-prod-config.yaml'

## BUILD ------------------------
#  - Settings revealed at build/installation time
#  - Only known after some setup or build step is completed
PACKAGE_VERSION = get_version_object()

API_MAJOR_VERSION = PACKAGE_VERSION.major
API_URL_VERSION = "v{:.0f}".format(API_MAJOR_VERSION)


## KEYS -------------------------
# TODO: test no key collisions
# Keys used in different scopes. Common naming format:
#
#    $(SCOPE)_$(NAME)_KEY
#

# APP=application
APP_CONFIG_KEY = application_keys.APP_CONFIG_KEY
APP_OPENAPI_SPECS_KEY = application_keys.APP_OPENAPI_SPECS_KEY

APP_DB_ENGINE_KEY  = 'db_engine'
APP_DB_SESSION_KEY = 'db_session'

APP_DSM_THREADPOOL = "dsm_threadpool"

# CFG=configuration

# RSC=resource
RSC_OPENAPI_DIR_KEY = "oas3/{}".format(API_URL_VERSION)
RSC_OPENAPI_ROOTFILE_KEY = "{}/openapi.yaml".format(RSC_OPENAPI_DIR_KEY)
RSC_CONFIG_DIR_KEY  = "data"
RSC_CONFIG_SCHEMA_KEY = RSC_CONFIG_DIR_KEY + "/config-schema-v1.json"

# RQT=request
RQT_DSM_KEY = "DSM"

# RSP=response


## Settings revealed at runtime: only known when the application starts
#  - via the config file passed to the cli

OAS_ROOT_FILE = "{}/openapi.yaml".format(RSC_OPENAPI_DIR_KEY) # TODO: delete


__all__ = (
    'CONFIG_SCHEMA', # TODO: fill with proper values
)
