""" Facade for openapi functionality

"""
from pathlib import Path

import openapi_core
import yaml
from openapi_core.schema.exceptions import OpenAPIError, OpenAPIMappingError #pylint: disable=W0611
from openapi_core.schema.specs.models import Spec

# Supported version of openapi
OAI_VERSION = '3.0.1'
OAI_VERSION_URL = 'https://github.com/OAI/OpenAPI-Specification/blob/master/versions/%s.md'%OAI_VERSION

# TODO: ensure openapi_core.__version__ is up-to-date with OAI_VERSION

def create_specs(openapi_path: Path) -> Spec:
    with openapi_path.open() as f:
        spec_dict = yaml.safe_load(f)

    spec = openapi_core.create_spec(spec_dict, spec_url=openapi_path.as_uri())
    return spec


__all__ = (
    'create_specs',
    'OAI_VERSION',
    'Spec'
)
