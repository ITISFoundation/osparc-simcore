""" Restful API

    - Loads and validates openapi specifications (oas)
    - Adds check and diagnostic routes
    - Activates middlewares

"""
import logging

import openapi_core
import yaml
from aiohttp import web

from servicelib import openapi

from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_middlewares import append_rest_middlewares
from simcore_service_webserver.resources import resources

from . import rest_routes
from .rest_config import APP_OPENAPI_SPECS_KEY, get_rest_config

log = logging.getLogger(__name__)


@app_module_setup(__name__, ModuleCategory.ADDON,
    depends=['simcore_service_webserver.security'],
    logger=log)
def setup(app: web.Application):

    cfg = get_rest_config(app) # TODO: can be automaticaly injected by app_module_setup??

    try:
        # FIXME: openapi_core has a bug and cannot support additionalProperties: false/true
        api_version_dir = cfg["version"]
        spec_path = resources.get_path(f'api/{api_version_dir}/openapi.yaml')
        with spec_path.open() as fh:
            spec_dict = yaml.safe_load(fh)
        specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())

        # TODO: should freeze specs here??
        app[APP_OPENAPI_SPECS_KEY] = specs # validated openapi specs

        # version check
        base_path = openapi.get_base_path(specs)
        major, *_ = specs.info.version
        assert f"/v{major}" == base_path, \
            f"Basepath naming {base_path} does not fit API version {specs.info.version}"

        # diagnostics routes
        routes = rest_routes.create(specs)
        app.router.add_routes(routes)

        # middelwares
        append_rest_middlewares(app, base_path)

    except openapi.OpenAPIError:
        # TODO: protocol when some parts are unavailable because of failure
        # Define whether it is critical or this server can still
        # continue working offering partial services
        log.exception("Invalid rest API specs. Rest API is DISABLED")

# alias
setup_rest = setup

__all__ = (
    'setup_rest'
)
