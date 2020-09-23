""" Subsystem to communicate with catalog service

"""
import logging
from typing import Dict, List, Optional

from aiohttp import ContentTypeError, web
from yarl import URL

from servicelib.application_keys import APP_OPENAPI_SPECS_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_responses import wrap_as_envelope
from servicelib.rest_routing import iter_path_operations

from .__version__ import api_version_prefix
from .catalog_config import get_client_session, get_config
from .constants import RQ_PRODUCT_KEY, X_PRODUCT_NAME_HEADER
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required

logger = logging.getLogger(__name__)


async def is_service_responsive(app: web.Application):
    """ Returns true if catalog is ready """
    origin: URL = app.get(f"{__name__}.catalog_origin")

    if not origin:  # service was not enabled!
        return False

    client = get_client_session(app)

    # call to health-check entry-point
    async with client.get(origin, ssl=False) as resp:
        return resp.status == 200


def to_backend_service(rel_url: URL, origin: URL, version_prefix: str) -> URL:
    """Translates relative url to backend catalog service url

    E.g. https://osparc.io/v0/catalog/dags -> http://catalog:8080/v0/dags
    """
    assert not rel_url.is_absolute()  # nosec
    new_path = rel_url.path.replace(
        f"/{api_version_prefix}/catalog", f"/{version_prefix}"
    )
    return origin.with_path(new_path).with_query(rel_url.query)


async def _request_catalog(
    app: web.Application,
    method: str,
    url: URL,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
) -> web.Response:
    session = get_client_session(app)

    async with session.request(method, url, headers=headers, data=data) as resp:

        is_error = resp.status >= 400
        # catalog backend sometimes sends error in plan=in text
        try:
            payload: Dict = await resp.json()
        except ContentTypeError:
            payload = await resp.text()
            is_error = True

        if is_error:
            # Only if error, it wraps since catalog service does not return (for the moment) enveloped
            data = wrap_as_envelope(error=payload)
        else:
            data = wrap_as_envelope(data=payload)

        return web.json_response(data, status=resp.status)


## HANDLERS  ------------------------


@login_required
@permission_required("services.catalog.*")
async def _reverse_proxy_handler(request: web.Request) -> web.Response:
    """
        - Adds auth layer
        - Adds access layer
        - Forwards request to catalog service

    SEE https://gist.github.com/barrachri/32f865c4705f27e75d3b8530180589fb
    """
    user_id = request[RQT_USERID_KEY]

    # path & queries
    backend_url = to_backend_service(
        request.rel_url,
        request.app[f"{__name__}.catalog_origin"],
        request.app[f"{__name__}.catalog_version_prefix"],
    )
    # FIXME: hack
    if "/services" in backend_url.path:
        backend_url = backend_url.update_query({"user_id": user_id})
    logger.debug("Redirecting '%s' -> '%s'", request.url, backend_url)

    # body
    raw = None
    if request.can_read_body:
        raw: bytes = await request.read()

    # injects product discovered by middleware in headers
    fwd_headers = request.headers.copy()
    product_name = request[RQ_PRODUCT_KEY]
    fwd_headers.update({X_PRODUCT_NAME_HEADER: product_name})

    # forward request
    return await _request_catalog(
        request.app, request.method, backend_url, fwd_headers, raw
    )


## API ------------------------


async def get_services_for_user_in_product(
    app: web.Application, user_id: int, product_name: str, *, only_key_versions: bool
) -> Optional[List[Dict]]:
    url = (
        URL(app[f"{__name__}.catalog_origin"])
        .with_path(app[f"{__name__}.catalog_version_prefix"] + "/services")
        .with_query({"user_id": user_id, "details": f"{not only_key_versions}"})
    )
    session = get_client_session(app)
    async with session.get(url, headers={X_PRODUCT_NAME_HEADER: product_name}) as resp:
        if resp.status >= 400:
            logger.error("Error while retrieving services for user %s", user_id)
            return
        return await resp.json()


## SETUP ------------------------


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup_catalog(app: web.Application, *, disable_auth=False):

    # resolve url
    cfg = get_config(app).copy()
    app[f"{__name__}.catalog_origin"] = URL.build(
        scheme="http", host=cfg["host"], port=cfg["port"]
    )
    app[f"{__name__}.catalog_version_prefix"] = cfg["version"]

    specs = app[APP_OPENAPI_SPECS_KEY]  # validated openapi specs

    # bind routes with handlers
    handler = (
        _reverse_proxy_handler.__wrapped__ if disable_auth else _reverse_proxy_handler
    )
    routes = [
        web.route(method.upper(), path, handler, name=operation_id)
        for method, path, operation_id, tags in iter_path_operations(specs)
        if "catalog" in tags
    ]
    assert routes, "Got no paths tagged as catalog"  # nosec

    # reverse proxy to catalog's API
    app.router.add_routes(routes)
