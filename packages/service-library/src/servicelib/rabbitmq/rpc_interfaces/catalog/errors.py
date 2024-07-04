from typing import Any

from models_library.errors_classes import OsparcErrorMixin


class CatalogApiBaseError(OsparcErrorMixin, Exception):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)


class CatalogItemNotFoundError(CatalogApiBaseError):
    msg_template = "{name} was not found"


class CatalogForbiddenError(CatalogApiBaseError):
    msg_template = "Does not have sufficient rights to access {name}"
