from common_library.errors_classes import OsparcErrorMixin


class CatalogRpcError(OsparcErrorMixin, Exception):
    pass


class CatalogInconsistentRpcError(CatalogRpcError):
    msg_template = "Catalog is inconsistent: The following  services are in the database but missing in the registry manifest {missing_services}"


class CatalogItemNotFoundRpcError(CatalogRpcError):
    msg_template = "{name} was not found"


class CatalogBatchNotFoundRpcError(CatalogRpcError):
    msg_template = "{name} were not found"


class CatalogForbiddenRpcError(CatalogRpcError):
    msg_template = "Insufficient access rights for {name}"


class CatalogNotAvailableRpcError(CatalogRpcError):
    msg_template = "Catalog service is currently not available"


class CatalogBadRequestRpcError(CatalogRpcError):
    msg_template = "Bad request on {name}: {reason}"
