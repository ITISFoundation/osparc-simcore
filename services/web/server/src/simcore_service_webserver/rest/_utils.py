from pathlib import Path

from .._meta import api_version_prefix
from .._resources import webserver_resources


def get_openapi_specs_path(api_version_dir: str | None = None) -> Path:
    if api_version_dir is None:
        api_version_dir = api_version_prefix

    oas_path: Path = webserver_resources.get_path(f"api/{api_version_dir}/openapi.yaml")
    return oas_path
