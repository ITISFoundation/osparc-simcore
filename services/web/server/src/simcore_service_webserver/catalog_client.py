""" Requests to catalog service API

"""
import asyncio
import logging
import urllib.parse
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientResponseError,
    InvalidURL,
)
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.rest_responses import wrap_as_envelope
from servicelib.json_serialization import json_dumps
from yarl import URL

from ._meta import api_version_prefix
from .catalog_config import KCATALOG_ORIGIN, KCATALOG_VERSION_PREFIX
from .constants import X_PRODUCT_NAME_HEADER

logger = logging.getLogger(__name__)


async def is_service_responsive(app: web.Application):
    """Returns true if catalog is ready"""
    try:
        origin: Optional[URL] = app.get(KCATALOG_ORIGIN)
        if not origin:
            raise ValueError(
                "KCATALOG_ORIGIN was not initialized (app module was not enabled?)"
            )

        client: ClientSession = get_client_session(app)
        await client.get(
            origin,
            ssl=False,
            raise_for_status=True,
            timeout=ClientTimeout(total=2, connect=1),
        )

    except (ClientConnectionError, ClientResponseError, InvalidURL, ValueError) as err:
        logger.warning("Catalog service unresponsive: %s", err)
        return False
    else:
        return True


def to_backend_service(rel_url: URL, origin: URL, version_prefix: str) -> URL:
    """Translates relative url to backend catalog service url

    E.g. https://osparc.io/v0/catalog/dags -> http://catalog:8080/v0/dags
    """
    assert not rel_url.is_absolute()  # nosec
    new_path = rel_url.path.replace(
        f"/{api_version_prefix}/catalog", f"/{version_prefix}"
    )
    return origin.with_path(new_path).with_query(rel_url.query)


async def make_request_and_envelope_response(
    app: web.Application,
    method: str,
    url: URL,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
) -> web.Response:
    """
    Helper to forward a request to the catalog service
    """
    session = get_client_session(app)

    try:

        async with session.request(method, url, headers=headers, data=data) as resp:
            payload = await resp.json()

            try:
                resp.raise_for_status()
                resp_data = wrap_as_envelope(data=payload)

            except ClientResponseError as err:
                if 500 <= err.status:
                    raise err
                resp_data = wrap_as_envelope(error=payload["errors"])

            return web.json_response(resp_data, status=resp.status, dumps=json_dumps)

    except (asyncio.TimeoutError, ClientConnectionError, ClientResponseError) as err:
        logger.warning(
            "Catalog service errors upon request %s %s: %s", method, url.relative(), err
        )
        raise web.HTTPServiceUnavailable(
            reason="catalog is currently unavailable"
        ) from err


## API ------------------------


async def get_services_for_user_in_product(
    app: web.Application, user_id: int, product_name: str, *, only_key_versions: bool
) -> List[Dict]:
    url = (
        URL(app[KCATALOG_ORIGIN])
        .with_path(app[KCATALOG_VERSION_PREFIX] + "/services")
        .with_query({"user_id": user_id, "details": f"{not only_key_versions}"})
    )
    session = get_client_session(app)
    try:
        async with session.get(
            url,
            headers={X_PRODUCT_NAME_HEADER: product_name},
        ) as resp:
            if resp.status >= 400:
                logger.warning(
                    "Error while retrieving services for user %s. Returning an empty list",
                    user_id,
                )
                return []
            return await resp.json()
    except asyncio.TimeoutError as err:
        logger.warning("Catalog service connection timeout error")
        raise web.HTTPServiceUnavailable(
            reason="catalog is currently unavailable"
        ) from err


async def get_service(
    app: web.Application,
    user_id: int,
    service_key: str,
    service_version: str,
    product_name: str,
) -> Dict[str, Any]:
    url = (
        URL(app[KCATALOG_ORIGIN])
        .with_path(
            app[KCATALOG_VERSION_PREFIX]
            + f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
        )
        .with_query(
            {
                "user_id": user_id,
            }
        )
    )
    session = get_client_session(app)
    try:
        async with session.get(
            url, headers={X_PRODUCT_NAME_HEADER: product_name}
        ) as resp:
            resp.raise_for_status()  # FIXME: error handling for session and response exceptions
            return await resp.json()
    except asyncio.TimeoutError as err:
        logger.warning("Catalog service connection timeout error")
        raise web.HTTPServiceUnavailable(
            reason="catalog is currently unavailable"
        ) from err


async def update_service(
    app: web.Application,
    user_id: int,
    service_key: str,
    service_version: str,
    product_name: str,
    update_data: Dict[str, Any],
) -> Dict[str, Any]:
    url = (
        URL(app[KCATALOG_ORIGIN])
        .with_path(
            app[KCATALOG_VERSION_PREFIX]
            + f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
        )
        .with_query(
            {
                "user_id": user_id,
            }
        )
    )
    session = get_client_session(app)
    try:
        async with session.patch(
            url, headers={X_PRODUCT_NAME_HEADER: product_name}, json=update_data
        ) as resp:
            resp.raise_for_status()  # FIXME: error handling for session and response exceptions
            return await resp.json()
    except asyncio.TimeoutError as err:
        logger.warning("Catalog service connection timeout error")
        raise web.HTTPServiceUnavailable(
            reason="catalog is currently unavailable"
        ) from err
