""" Requests to catalog service API

"""
import logging
from typing import Dict, List, Optional, Union

from aiohttp import ContentTypeError, web
from servicelib.rest_responses import wrap_as_envelope
from yarl import URL

from ._meta import api_version_prefix
from .catalog_config import get_client_session
from .constants import X_PRODUCT_NAME_HEADER

logger = logging.getLogger(__name__)


async def is_service_responsive(app: web.Application):
    """ Returns true if catalog is ready """
    origin: Optional[URL] = app.get(f"{__name__}.catalog_origin")

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


async def make_request(
    app: web.Application,
    method: str,
    url: URL,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
) -> web.Response:
    """
    Helper to make request to catalog service
    """
    session = get_client_session(app)

    try:
        async with session.request(method, url, headers=headers, data=data) as resp:

            is_error = resp.status >= 400
            # catalog backend sometimes sends error in plan=in text
            payload: Union[Dict, str] = {}
            try:
                payload = await resp.json()
            except ContentTypeError:
                payload = await resp.text()
                is_error = True

            if is_error:
                # Only if error, it wraps since catalog service does
                # not return (for the moment) enveloped
                data = wrap_as_envelope(error=payload)
            else:
                data = wrap_as_envelope(data=payload)

            return web.json_response(data, status=resp.status)

    except (TimeoutError,) as err:
        raise web.HTTPServiceUnavailable(reason="unavailable catalog service") from err


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
