""" Subsystem to communicate with catalog service

"""
import logging

from aiohttp import web

from yarl import URL

from servicelib.application_keys import APP_OPENAPI_SPECS_KEY

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

logger = logging.getLogger(__name__)


async def _forward(url: str, request: web.Request):
    # forward
    body = None
    if request.can_read_body:
        body = await request.json()

    session = get_client_session(request.app)
    async with session.request(request.method, url, ssl=False, json=body) as resp:
        payload = await resp.json()
        return payload


@app_module_setup(__name__, ModuleCategory.ADDON,
    depends=[],
    logger=logger)
def setup_catalog(app: web.Application):


    specs = app[APP_OPENAPI_SPECS_KEY] # validated openapi specs
    # TODO: filter by tag??


    # bind routes with redirects? some decoration?
    # auth layer
    # access layer

    # resolve url
    # GET https://osparc.io/v0/dags -> http://catalog:8080/v0/dags
    #



    # forward layer (resolve )
    cfg = app[APP_CONFIG_KEY]
    base_url = URL.build(scheme='http', host=cfg['host'], port=cfg['port']).with_path(cfg["version"])






    # reverse proxy to catalog's API
    app.router.add_routes()
