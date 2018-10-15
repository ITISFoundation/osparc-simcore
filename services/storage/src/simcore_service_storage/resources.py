""" Access to data resources installed with this package

"""
from pathlib import Path
from simcore_servicelib.resources import Resources

from .settings import RSC_CONFIG_KEY, RSC_OPENAPI_KEY #pylint: disable=unused-import
from .settings import OAS_ROOT_FILE

resources = Resources(__name__, config_folder='etc/simcore_service_storage')


def openapi_path() -> Path:
    """ Returns path to the roots's oas file
    Notice that the specs can be split in multiple files. Thisone
    is the root file and it is normally named as `opeapi.yaml`
    """
    return resources.get_path(OAS_ROOT_FILE)


__all__ = (
    'resources',
    'RSC_CONFIG_KEY',
    'RSC_OPENAPI_KEY'
)