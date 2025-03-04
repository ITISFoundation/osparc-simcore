"""Defines the different exceptions that may arise in the catalog subpackage"""

import functools

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)

from ..errors import WebServerBaseError
from ..resource_usage.errors import DefaultPricingPlanNotFoundError


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


class BaseCatalogError(WebServerBaseError):
    msg_template = "Unexpected error occured in catalog submodule"

    def __init__(self, msg=None, **ctx):
        super().__init__(**ctx)
        if msg:
            self.msg_template = msg

    def debug_message(self):
        # Override in subclass
        return f"{self.code}: {self}"


class DefaultPricingUnitForServiceNotFoundError(BaseCatalogError):
    msg_template = "Default pricing unit not found for service key '{service_key}' and version '{service_version}'"

    def __init__(self, *, service_key: str, service_version: str, **ctxs):
        super().__init__(**ctxs)
        self.service_key = service_key
        self.service_version = service_version


# mypy: disable-error-code=truthy-function
assert CatalogForbiddenError  # nosec
assert CatalogItemNotFoundError  # nosec


__all__: tuple[str, ...] = (
    "CatalogForbiddenError",
    "CatalogItemNotFoundError",
    "DefaultPricingUnitForServiceNotFoundError",
)
