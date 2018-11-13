""" Facade for openapi functionality

"""
import warnings
from pathlib import Path
from typing import Dict, Tuple

import yaml

import openapi_core
from aiohttp import ClientSession
from openapi_core.schema.exceptions import OpenAPIError, OpenAPIMappingError  # pylint: disable=W0611
from openapi_core.schema.specs.models import Spec
from yarl import URL

# Supported version of openapi
OAI_VERSION = '3.0.1'
OAI_VERSION_URL = 'https://github.com/OAI/OpenAPI-Specification/blob/master/versions/%s.md'%OAI_VERSION

# alias
OpenApiSpec = Spec


# TODO: ensure openapi_core.__version__ is up-to-date with OAI_VERSION



def load_from_path(filepath: Path) -> Tuple[Dict, str]:
    with filepath.open() as f:
        spec_dict = yaml.safe_load(f)
        return spec_dict, filepath.as_uri()


async def load_from_url(url: URL) -> Tuple[Dict, str]:
    #TIMEOUT_SECS = 5*60
    #async with ClientSession(timeout=TIMEOUT_SECS) as session:
    async with ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            spec_dict = yaml.safe_load(text)
            return spec_dict, str(url)


async def create_openapi_specs(location: str) -> OpenApiSpec:
    if URL(location).host:
        spec_dict, spec_url = await load_from_url(URL(location))
    else:
        path = Path(location).expanduser().resolve()
        spec_dict, spec_url = load_from_path(path)

    return openapi_core.create_spec(spec_dict, spec_url)



def create_specs(openapi_path: Path) -> OpenApiSpec:
    warnings.warn("Use instead create_openapi_specs",
        category=DeprecationWarning)


    # TODO: spec_from_file and spec_from_url
    with openapi_path.open() as f:
        spec_dict = yaml.safe_load(f)

    spec = openapi_core.create_spec(spec_dict, spec_url=openapi_path.as_uri())
    return spec


def get_base_path(specs: OpenApiSpec) ->str :
    # TODO: guarantee this convention is true
    return '/v' + specs.info.version.split('.')[0]


__all__ = (
    'create_specs',
    'OAI_VERSION',
    'Spec'
)
