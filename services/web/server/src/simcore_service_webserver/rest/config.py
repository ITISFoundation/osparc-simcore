""" REST-api configuration

 - Set here the version of API to be used
 - Versions and name consistency tested in test_rest.py
"""
from pathlib import Path
import yaml

from .. import resources

API_MAJOR_VERSION = 1
API_URL_PREFIX = "v{:.0f}".format(API_MAJOR_VERSION)
API_SPECS_NAME = ".oas3/{}/openapi.yaml".format(API_URL_PREFIX)

def api_version() -> str:
    specs = yaml.load(resources.stream(API_SPECS_NAME))
    return specs['info']['version']

def api_specification_path() -> Path:
    return resources.get_path(API_SPECS_NAME)


__all__ = (
    'API_MAJOR_VERSION',
    'API_URL_PREFIX',
    'api_version',
    'api_specification_path'
)
