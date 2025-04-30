from common_library.errors_classes import OsparcErrorMixin


class CatalogApiBaseError(OsparcErrorMixin, Exception):
    pass


class CatalogInconsistentError(CatalogApiBaseError):
    msg_template = "Catalog is inconsistent: The following  services are in the database but missing in the registry manifest {missing_services}"


class CatalogItemNotFoundError(CatalogApiBaseError):
    msg_template = "{name} was not found"


class CatalogForbiddenError(CatalogApiBaseError):
    msg_template = "Insufficient access rights for {name}"


class CatalogNotAvailableError(CatalogApiBaseError):
    msg_template = "Catalog service failed unexpectedly"
