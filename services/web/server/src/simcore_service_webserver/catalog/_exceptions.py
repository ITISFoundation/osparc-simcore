"""Defines the different exceptions that may arise in the catalog subpackage"""

from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)

from ..errors import WebServerBaseError
from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..resource_usage.errors import DefaultPricingPlanNotFoundError


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


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    CatalogItemNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Catalog item not found",
    ),
    DefaultPricingPlanNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Default pricing plan not found",
    ),
    DefaultPricingUnitForServiceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND, "Default pricing unit not found"
    ),
    CatalogForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN, "Forbidden catalog access"
    ),
}

handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)


__all__: tuple[str, ...] = (
    "CatalogForbiddenError",
    "CatalogItemNotFoundError",
    "DefaultPricingUnitForServiceNotFoundError",
)
