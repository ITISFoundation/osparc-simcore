from common_library.errors_classes import OsparcErrorMixin


class BaseCatalogError(OsparcErrorMixin, Exception): ...


class RepositoryError(BaseCatalogError):
    msg_template = "Unexpected error in {repo_cls}"


class UninitializedGroupError(RepositoryError):
    msg_tempalte = "{group} groups was never initialized"


class BaseDirectorError(BaseCatalogError): ...


class DirectorUnresponsiveError(BaseDirectorError):
    msg_template = "Director-v0 is not responsive"


class DirectorStatusError(BaseDirectorError): ...


class BatchNotFoundError(BaseCatalogError):
    msg_template = "None of the batch services were found in the catalog. Missing: {missing_services}"
