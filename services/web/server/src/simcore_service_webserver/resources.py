""" Access to data resources installed within this package

"""
from servicelib.resources import ResourcesFacade

# pylint: disable=unused-import
from .resources_keys import (RSC_CONFIG_DIR_KEY,
                                     RSC_OPENAPI_DIR_KEY)

resources = ResourcesFacade(
    package_name=__name__,
    distribution_name="simcore-service-webserver",
    config_folder='config',
)


__all__ = (
    'resources',
    'RSC_CONFIG_DIR_KEY',
    'RSC_OPENAPI_DIR_KEY'
)


#TODO: from servicelib import resources

# resources names
# TODO: import all RSC_* within .settings.constants!
#RESOURCE_OPENAPI = "oas3"
#RESOURCE_CONFIG  = "config"
