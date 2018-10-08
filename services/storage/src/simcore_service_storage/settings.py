""" Configuration of simcore_service_storage

The application can consume settings revealed at different
stages of the development workflow. This submodule gives access
to all of them.

"""
import logging

from .__version__ import get_version_object

log = logging.getLogger(__name__)

## Constants: low-level tweals ...
TIMEOUT_IN_SECS = 2
RESOURCE_KEY_OPENAPI = "oas3/v0"

## Settings revealed at build/installation time: only known after some setup or build step is completed
PACKAGE_VERSION = get_version_object()


## Settings revealed at runtime: only known when the application starts 
#  - via the config file passed to the cli
