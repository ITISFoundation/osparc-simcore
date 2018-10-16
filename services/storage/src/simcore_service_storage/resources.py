""" Access to data resources installed with this package

"""
from pathlib import Path
from servicelib.resources import ResourcesFacade

from .settings import RSC_CONFIG_DIR_KEY, RSC_OPENAPI_DIR_KEY #pylint: disable=unused-import
from .settings import OAS_ROOT_FILE

resources = ResourcesFacade(
    package_name=__name__,
    distribution_name="simcore-service-storage",
    config_folder='etc/',
)


def openapi_path() -> Path:
    """ Returns path to the roots's oas file
    Notice that the specs can be split in multiple files. Thisone
    is the root file and it is normally named as `opeapi.yaml`
    """
    return resources.get_path(OAS_ROOT_FILE)


__all__ = (
    'resources',
    'RSC_CONFIG_DIR_KEY',
    'RSC_OPENAPI_DIR_KEY'
)
