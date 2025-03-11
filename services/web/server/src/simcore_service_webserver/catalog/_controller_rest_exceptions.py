"""Defines the different exceptions that may arise in the catalog subpackage"""

from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)

from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..resource_usage.errors import DefaultPricingPlanNotFoundError
from .errors import DefaultPricingUnitForServiceNotFoundError

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
