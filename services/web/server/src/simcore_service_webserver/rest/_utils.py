from functools import lru_cache
from pathlib import Path

import openapi_core
import yaml
from openapi_core.schema.specs.models import Spec as OpenApiSpecs

from .._meta import api_version_prefix
from .._resources import webserver_resources


def get_openapi_specs_path(api_version_dir: str | None = None) -> Path:
    if api_version_dir is None:
        api_version_dir = api_version_prefix

    oas_path: Path = webserver_resources.get_path(f"api/{api_version_dir}/openapi.yaml")
    return oas_path


@lru_cache  # required to boost tests speed, gains 3.5s per test
def load_openapi_specs(spec_path: Path | None = None) -> OpenApiSpecs:
    if spec_path is None:
        spec_path = get_openapi_specs_path()

    with spec_path.open() as fh:
        spec_dict = yaml.safe_load(fh)
    specs: OpenApiSpecs = openapi_core.create_spec(spec_dict, spec_path.as_uri())

    return specs
