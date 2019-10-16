""" Openapi specifications

    Facade for openapi functionality
"""
import warnings
from pathlib import Path
from typing import Dict, Optional, Tuple

import openapi_core
import yaml
from aiohttp import ClientSession
from openapi_core.schema.exceptions import OpenAPIError, OpenAPIMappingError
from openapi_core.schema.specs.models import Spec as OpenApiSpec
from yarl import URL

from .utils import resolve_location

# Supported version of openapi (last number indicates only editorial changes)
# TODO: ensure openapi_core.__version__ is up-to-date with OAI_VERSION
OAI_VERSION = '3.0.2'
OAI_VERSION_URL = 'https://github.com/OAI/OpenAPI-Specification/blob/master/versions/%s.md'%OAI_VERSION


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


def create_specs_from_path(filepath: Path) -> Tuple[Dict, str]:
    with filepath.open() as fh:
        spec_dict = yaml.safe_load(fh)
        spec_obj = openapi_core.create_spec(spec_dict, filepath.as_uri())
        return spec_obj

async def create_specs_from_url(session: ClientSession, url: URL) -> Tuple[Dict, str]:
    async with session.get(url) as resp:
        text = await resp.text()
        spec_dict = yaml.safe_load(text)
        spec_obj = openapi_core.create_spec(spec_dict, str(url))
        return spec_obj

async def create_openapi_specs(location, session: Optional[ClientSession]=None) -> OpenApiSpec:
    """ Loads specs from a given location (url or path),
        validates them and returns a working instance

    If location is an url, the specs are loaded asyncronously

    Use create_specs_from_url or create_specs_from_path if the location is known

    Both location types (url and file) are intentionally managed
    by the same function call to enforce developer always supporting
    both options. Notice that the url location enforces
    the consumer context to be asyncronous.
    """
    loc = resolve_location(location)

    if isinstance(loc, URL):
        if session is None:
            raise ValueError("Client session required in arguments")
        return await create_specs_from_url(session, loc)

    assert isinstance(loc, Path)
    return create_specs_from_path(loc)


# DEPRECATED
def create_specs(openapi_path: Path) -> OpenApiSpec:
    warnings.warn("Use instead create_openapi_specs",
        category=DeprecationWarning)

    with openapi_path.open() as f:
        spec_dict = yaml.safe_load(f)

    spec = openapi_core.create_spec(spec_dict, spec_url=openapi_path.as_uri())
    return spec



__all__ = (
    'get_base_path',
    'create_openapi_specs',
    'OpenApiSpec',
    'OpenAPIError',
    'OpenAPIMappingError'
)
