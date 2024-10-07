from typing import Any

from common_library.errors_classes import OsparcErrorMixin


class CatalogApiBaseError(OsparcErrorMixin, Exception):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)


class CatalogItemNotFoundError(CatalogApiBaseError):
    msg_template = "{name} was not found"


class CatalogForbiddenError(CatalogApiBaseError):
    msg_template = "Insufficient access rights for {name}"
