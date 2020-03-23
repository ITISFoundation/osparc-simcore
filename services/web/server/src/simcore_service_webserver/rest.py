""" Restful API

    - Loads and validates openapi specifications (oas)
    - Adds check and diagnostic routes
    - Activates middlewares

"""
import logging
from pathlib import Path
from typing import Optional

import openapi_core
import yaml
from aiohttp import web
from aiohttp_swagger import setup_swagger
from openapi_core.schema.specs.models import Spec as OpenApiSpecs

from servicelib import openapi
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_middlewares import append_rest_middlewares
from simcore_service_webserver.resources import resources

from . import rest_routes
from .__version__ import api_version_prefix
from .rest_config import APP_OPENAPI_SPECS_KEY, get_rest_config

log = logging.getLogger(__name__)


def get_openapi_specs_path(api_version_dir: Optional[str] = None) -> Path:
    if api_version_dir is None:
        api_version_dir = api_version_prefix

    return resources.get_path(f"api/{api_version_dir}/openapi.yaml")


def load_openapi_specs(spec_path: Optional[Path] = None) -> OpenApiSpecs:
    if spec_path is None:
        spec_path = get_openapi_specs_path()

    with spec_path.open() as fh:
        spec_dict = yaml.safe_load(fh)
    specs: OpenApiSpecs = openapi_core.create_spec(spec_dict, spec_path.as_uri())

    return specs



@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.security"],
    logger=log,
)
def setup(app: web.Application):
    cfg = get_rest_config(app)
    api_version_dir = cfg["version"]
    spec_path = get_openapi_specs_path(api_version_dir)

    # validated openapi specs
    app[APP_OPENAPI_SPECS_KEY] = specs = load_openapi_specs(spec_path)

    # version check
    base_path = openapi.get_base_path(specs)
    major, *_ = specs.info.version

    if f"/v{major}" != base_path:
        raise ValueError(
            f"Basepath naming {base_path} does not fit API version {specs.info.version}"
        )

    # diagnostics routes
    routes = rest_routes.create(specs)
    app.router.add_routes(routes)

    # middlewares
    append_rest_middlewares(app, base_path)

    # rest API doc at /api/doc
    log.debug("OAS loaded from %s ", spec_path)
    setup_swagger(app, swagger_from_file=str(spec_path), ui_version=3)


# alias
setup_rest = setup

__all__ = "setup_rest"
