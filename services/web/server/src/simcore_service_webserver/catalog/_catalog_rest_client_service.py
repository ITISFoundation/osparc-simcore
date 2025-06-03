"""Requests to catalog service API"""

import logging
import urllib.parse
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Final

from aiocache import Cache, cached  # type: ignore[import-untyped]
from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientResponseError,
    InvalidURL,
)
from models_library.api_schemas_catalog.service_access_rights import (
    ServiceAccessRightsGet,
)
from models_library.products import ProductName
from models_library.services_resources import ServiceResourcesDict
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.client_session import get_client_session
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from yarl import URL

from .._meta import api_version_prefix
from ._constants import MSG_CATALOG_SERVICE_NOT_FOUND, MSG_CATALOG_SERVICE_UNAVAILABLE
from .settings import CatalogSettings, get_plugin_settings

_logger = logging.getLogger(__name__)

# Cache settings
_SECOND = 1  # in seconds
_MINUTE = 60 * _SECOND
_CACHE_TTL: Final = 1 * _MINUTE


def _create_service_cache_key_(_f: Callable[..., Any], *_args, **kw):
    assert len(_args) == 1, f"Expected only app, got {_args}"  # nosec
    return f"get_service_{kw['user_id']}_{kw['service_key']}_{kw['service_version']}_{kw['product_name']}"


@contextmanager
def _handle_client_exceptions(app: web.Application) -> Iterator[ClientSession]:
    try:
        session: ClientSession = get_client_session(app)

        yield session

    except ClientResponseError as err:
        if err.status == status.HTTP_404_NOT_FOUND:
            raise web.HTTPNotFound(text=MSG_CATALOG_SERVICE_NOT_FOUND) from err
        raise web.HTTPServiceUnavailable(
            reason=MSG_CATALOG_SERVICE_UNAVAILABLE
        ) from err

    except (TimeoutError, ClientConnectionError) as err:
        _logger.debug("Request to catalog service failed: %s", err)
        raise web.HTTPServiceUnavailable(
            reason=MSG_CATALOG_SERVICE_UNAVAILABLE
        ) from err


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
            if not response.ok:
                _logger.warning(
                    "Error while retrieving services for user %s. Returning an empty list",
                    user_id,
                )
                return []
            body: list[dict] = await response.json()
            return body


@cached(
    ttl=_CACHE_TTL,
    key_builder=_create_service_cache_key_,
    cache=Cache.MEMORY,
)
async def get_service(
    app: web.Application,
    *,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    product_name: ProductName,
) -> dict[str, Any]:
    settings: CatalogSettings = get_plugin_settings(app)
    url = URL(
        f"{settings.api_base_url}/services/{urllib.parse.quote_plus(service_key)}/{service_version}",
        encoded=True,
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
        URL(
            f"{settings.api_base_url}/services/{urllib.parse.quote_plus(service_key)}/{service_version}/resources",
            encoded=True,
        )
    ).with_query({"user_id": user_id})

    with _handle_client_exceptions(app) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            dict_response = await resp.json()
            return TypeAdapter(ServiceResourcesDict).validate_python(dict_response)


async def get_service_access_rights(
    app: web.Application,
    user_id: UserID,
    service_key: str,
    service_version: str,
    product_name: str,
) -> ServiceAccessRightsGet:
    settings: CatalogSettings = get_plugin_settings(app)
    url = URL(
        f"{settings.api_base_url}/services/{urllib.parse.quote_plus(service_key)}/{service_version}/accessRights",
        encoded=True,
    ).with_query({"user_id": user_id})

    with _handle_client_exceptions(app) as session:
        async with session.get(
            url, headers={X_PRODUCT_NAME_HEADER: product_name}
        ) as resp:
            resp.raise_for_status()
            body = await resp.json()
            return ServiceAccessRightsGet.model_validate(body)
