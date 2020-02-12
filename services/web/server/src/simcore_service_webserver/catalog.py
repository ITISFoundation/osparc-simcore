""" Subsystem to communicate with catalog service

"""
import logging

from aiohttp import web
from yarl import URL

from servicelib.application_keys import APP_OPENAPI_SPECS_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_routing import iter_path_operations

from .__version__ import api_version_prefix
from .catalog_config import get_client_session, get_config
from .login.decorators import login_required

logger = logging.getLogger(__name__)


#TODO: from servicelib.rest_responses import wrap_envelope
#TODO: from .security_api import check_permission


async def is_service_responsive(app:web.Application):
    """ Returns true if catalog is ready """
    origin: URL = app.get(f'{__name__}.catalog_origin')

    if not origin: # service was not enabled!
        return False

    client = get_client_session(app)

    # call to health-check entry-point
    async with client.get(origin, ssl=False) as resp:
        return resp.status == 200


def to_backend_service(rel_url: URL, origin: URL, version_prefix: str) -> URL:
    """ Translates relative url to backend catalog service url

        E.g. https://osparc.io/v0/catalog/dags -> http://catalog:8080/v0/dags
    """
    assert not rel_url.is_absolute() # nosec
    new_path = rel_url.path.replace(f"/{api_version_prefix}/catalog", f"/{version_prefix}")
    return origin.with_path(new_path).with_query(rel_url.query)



@login_required
async def _reverse_proxy_handler(request: web.Request):
    """
        - Adds auth layer
        - Adds access layer
        - Forwards request to catalog service
    """
    # TODO: await check_permission

    # path & queries
    backend_url = to_backend_service(
        request.rel_url,
        request.app[f'{__name__}.catalog_origin'],
        request.app[f'{__name__}.catalog_version_prefix']
    )
    logger.debug("Redirecting '%s' -> '%s'", request.url, backend_url)

    # TODO: there must be a way to simply forward everything to
    # body
    body = None
    if request.can_read_body:
        body = await request.json()

    #TODO: header?

    # forward request
    client = get_client_session(request.app)
    async with client.request(request.method, backend_url, ssl=False, json=body) as resp:
        data = await resp.json()
        if resp.status >= 300: # if error
            #T
            pass
            # TODO: create proper error enveloped unwrap_envelope
        return data


@app_module_setup(__name__, ModuleCategory.ADDON,
    depends=['simcore_service_webserver.rest'],
    logger=logger)
def setup_catalog(app: web.Application):

    # resolve url
    cfg = get_config(app).copy()
    app[f'{__name__}.catalog_origin'] = URL.build(scheme='http', host=cfg['host'], port=cfg['port'])
    app[f'{__name__}.catalog_version_prefix'] = cfg['version']

    specs = app[APP_OPENAPI_SPECS_KEY] # validated openapi specs

    # bind routes with handlers
    routes = [ web.route(method.upper(), path, _reverse_proxy_handler, name=operation_id)
        for method, path, operation_id, tags in iter_path_operations(specs)
            if 'catalog' in tags
    ]
    assert routes, "Got no paths tagged as catalog"

    # reverse proxy to catalog's API
    app.router.add_routes(routes)
