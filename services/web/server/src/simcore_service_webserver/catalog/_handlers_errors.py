import functools

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

from ..resource_usage.errors import DefaultPricingPlanNotFoundError
from ._exceptions import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
    DefaultPricingUnitForServiceNotFoundError,
)


def reraise_catalog_exceptions_as_http_errors(handler: Handler):
    @functools.wraps(handler)
    async def _wrapper(request: web.Request) -> web.StreamResponse:
        try:

            return await handler(request)

        except (
            CatalogItemNotFoundError,
            DefaultPricingPlanNotFoundError,
            DefaultPricingUnitForServiceNotFoundError,
        ) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except CatalogForbiddenError as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return _wrapper
