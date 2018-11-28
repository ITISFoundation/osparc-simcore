""" Openapi specifications

    Facade for openapi functionality
"""
import warnings
from pathlib import Path
from typing import Dict, Tuple

import openapi_core
import yaml
from aiohttp import ClientSession
from openapi_core.schema.exceptions import (OpenAPIError,  # pylint: disable=W0611
                                            OpenAPIMappingError)
from openapi_core.schema.specs.models import Spec
from yarl import URL

# Supported version of openapi (last number indicates only editorial changes)
# TODO: ensure openapi_core.__version__ is up-to-date with OAI_VERSION
OAI_VERSION = '3.0.2'
OAI_VERSION_URL = 'https://github.com/OAI/OpenAPI-Specification/blob/master/versions/%s.md'%OAI_VERSION

# alias
OpenApiSpec = Spec

def get_base_path(specs: OpenApiSpec) ->str:
    """ Expected API basepath

    By convention, the API basepath indicates the major
    version of the openapi specs

    :param specs: valid specifications
    :type specs: OpenApiSpec
    :return: /${MAJOR}
    :rtype: str
    """
    # TODO: guarantee this convention is true
    return '/v' + specs.info.version.split('.')[0]


def _load_from_path(filepath: Path) -> Tuple[Dict, str]:
    with filepath.open() as f:
        spec_dict = yaml.safe_load(f)
        return spec_dict, filepath.as_uri()


async def _load_from_url(url: URL) -> Tuple[Dict, str]:
    #TIMEOUT_SECS = 5*60
    #async with ClientSession(timeout=TIMEOUT_SECS) as session:
    async with ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            spec_dict = yaml.safe_load(text)
            return spec_dict, str(url)


async def create_openapi_specs(location) -> OpenApiSpec:
    """ Loads specs from a given location (url or path),
        validates them and returns a working instance

    If location is an url, the specs are loaded asyncronously

    Both location types (url and file) are intentionally managed
    by the same function call to enforce developer always supporting
    both options. Notice that the url location enforces
    the consumer context to be asyncronous.

    :param location: url or path
    :return: validated openapi specifications object
    :rtype: OpenApiSpec
    """
    if URL(str(location)).host:
        spec_dict, spec_url = await _load_from_url(URL(location))
    else:
        path = Path(location).expanduser().resolve()
        spec_dict, spec_url = _load_from_path(path)

    return openapi_core.create_spec(spec_dict, spec_url)



def create_specs(openapi_path: Path) -> OpenApiSpec:
    warnings.warn("Use instead create_openapi_specs",
        category=DeprecationWarning)


    # TODO: spec_from_file and spec_from_url
    with openapi_path.open() as f:
        spec_dict = yaml.safe_load(f)

    spec = openapi_core.create_spec(spec_dict, spec_url=openapi_path.as_uri())
    return spec



__all__ = (
    'get_base_path',
    'create_openapi_specs',
    'OpenApiSpec'
)
