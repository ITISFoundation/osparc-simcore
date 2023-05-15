""" Requests to catalog service API

"""
import asyncio
import logging
import urllib.parse
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientResponseError,
    InvalidURL,
)
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from pydantic import parse_obj_as
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.rest_responses import wrap_as_envelope
from servicelib.json_serialization import json_dumps
from settings_library.catalog import CatalogSettings
from yarl import URL

from .._constants import X_PRODUCT_NAME_HEADER
from .._meta import api_version_prefix
from ._constants import MSG_CATALOG_SERVICE_UNAVAILABLE
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def is_catalog_service_responsive(app: web.Application) -> bool:
    """Returns true if catalog is ready"""
    try:
        session: ClientSession = get_client_session(app)
        settings: CatalogSettings = get_plugin_settings(app)

        await session.get(
            settings.base_url,
            ssl=False,
            raise_for_status=True,
            timeout=ClientTimeout(total=2, connect=1),
        )
    except (ClientConnectionError, ClientResponseError, InvalidURL, ValueError):
        return False
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


@contextmanager
def _handle_client_exceptions(app: web.Application) -> Iterator[ClientSession]:
    try:
        session: ClientSession = get_client_session(app)

        yield session

    except (asyncio.TimeoutError, ClientConnectionError, ClientResponseError) as err:
        _logger.debug("Request to catalog service failed: %s", err)
        raise web.HTTPServiceUnavailable(
            reason=MSG_CATALOG_SERVICE_UNAVAILABLE
        ) from err


async def make_request_and_envelope_response(
    app: web.Application,
    method: str,
    url: URL,
    headers: Mapping[str, str] | None = None,
    data: bytes | None = None,
) -> web.Response:
    """
    Helper to forward a request to the catalog service
    """
    with _handle_client_exceptions(app) as session:

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


## API ------------------------


async def get_services_for_user_in_product(
    app: web.Application, user_id: UserID, product_name: str, *, only_key_versions: bool
) -> list[dict]:
    settings: CatalogSettings = get_plugin_settings(app)
    url = (URL(settings.api_base_url) / "services").with_query(
        {"user_id": user_id, "details": f"{not only_key_versions}"}
    )

    with _handle_client_exceptions(app) as session:

        async with session.get(
            url,
            headers={X_PRODUCT_NAME_HEADER: product_name},
        ) as response:
            if response.status >= 400:
                _logger.warning(
                    "Error while retrieving services for user %s. Returning an empty list",
                    user_id,
                )
                return []
            body: list[dict] = await response.json()
            return body


async def get_service(
    app: web.Application,
    user_id: UserID,
    service_key: str,
    service_version: str,
    product_name: str,
) -> dict[str, Any]:
    settings: CatalogSettings = get_plugin_settings(app)
    url = (
        URL(settings.api_base_url)
        / f"services/{urllib.parse.quote_plus(service_key)}/{service_version}"
    ).with_query({"user_id": user_id})

    with _handle_client_exceptions(app) as session:
        async with session.get(
            url, headers={X_PRODUCT_NAME_HEADER: product_name}
        ) as response:
            response.raise_for_status()
            body: dict[str, Any] = await response.json()
            return body


async def get_service_resources(
    app: web.Application,
    user_id: UserID,
    service_key: str,
    service_version: str,
) -> ServiceResourcesDict:
    settings: CatalogSettings = get_plugin_settings(app)
    url = (
        URL(settings.api_base_url)
        / f"services/{urllib.parse.quote_plus(service_key)}/{service_version}/resources"
    ).with_query({"user_id": user_id})

    with _handle_client_exceptions(app) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            dict_response = await resp.json()
            return parse_obj_as(ServiceResourcesDict, dict_response)


async def update_service(
    app: web.Application,
    user_id: UserID,
    service_key: str,
    service_version: str,
    product_name: str,
    update_data: dict[str, Any],
) -> dict[str, Any]:
    settings: CatalogSettings = get_plugin_settings(app)

    url = (
        URL(settings.api_base_url)
        / f"services/{urllib.parse.quote_plus(service_key)}/{service_version}"
    ).with_query({"user_id": user_id})

    with _handle_client_exceptions(app) as session:
        async with session.patch(
            url, headers={X_PRODUCT_NAME_HEADER: product_name}, json=update_data
        ) as resp:
            resp.raise_for_status()
            body: dict[str, Any] = await resp.json()
            return body
