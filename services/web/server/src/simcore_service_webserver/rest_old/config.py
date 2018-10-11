""" REST-api configuration

 - Set here the version of API to be used
 - Versions and name consistency tested in test_rest.py
"""
from pathlib import Path
import yaml

from .. import resources

API_MAJOR_VERSION = 1
API_URL_VERSION = "v{:.0f}".format(API_MAJOR_VERSION)
OAS_ROOT_FILE = "oas3/{}/openapi.yaml".format(API_URL_VERSION)

def api_version() -> str:
    specs = yaml.load(resources.stream(OAS_ROOT_FILE))
    return specs['info']['version']

def openapi_path() -> Path:
    """ Returns path to the roots's oas file

    Notice that the specs can be split in multiple files. Thisone
    is the root file and it is normally named as `opeapi.yaml`
    """
    return resources.get_path(OAS_ROOT_FILE)


__all__ = (
    'API_MAJOR_VERSION',
    'API_URL_VERSION',
    'api_version',
    'openapi_path'
)
