from common_library.errors_classes import OsparcErrorMixin


class CatalogApiBaseError(OsparcErrorMixin, Exception):
    pass


class CatalogItemNotFoundError(CatalogApiBaseError):
    msg_template = "{name} was not found"


class CatalogForbiddenError(CatalogApiBaseError):
    msg_template = "Insufficient access rights for {name}"
