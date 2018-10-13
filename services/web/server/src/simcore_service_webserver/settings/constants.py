""" Configuration of simcore_service_webserver

The application can consume settings revealed at different
stages of the development workflow. This submodule gives access
to all of them.


TODO: this should be the actual settings
"""
import logging

from simcore_servicelib.constants import (APP_CONFIG_KEY, APP_OAS_KEY,
                                         RSC_CONFIG_KEY)

from ..__version__ import get_version_object

log = logging.getLogger(__name__)

## CONSTANTS--------------------
TIMEOUT_IN_SECS = 2


## BUILD ------------------------
#  - Settings revealed at build/installation time
#  - Only known after some setup or build step is completed
package_version = get_version_object()

API_MAJOR_VERSION = package_version.major
API_URL_VERSION = "v{:.0f}".format(API_MAJOR_VERSION)


# STORAGE KEYS -------------------------
# Keys used in different scopes. Common naming format:
#
#    $(SCOPE)_$(NAME)_KEY
#
# See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please

# APP=application

# CFG=configuration

# RSC=resource
RSC_OPENAPI_KEY = "oas3/{}/openapi.yaml".format(API_URL_VERSION)

# RQT=request


# RSP=response


## Settings revealed at runtime: only known when the application starts
#  - via the config file passed to the cli
