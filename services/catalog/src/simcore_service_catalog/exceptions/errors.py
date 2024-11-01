from common_library.errors_classes import OsparcErrorMixin


class CatalogBaseError(OsparcErrorMixin, Exception):
    ...


class RepositoryError(CatalogBaseError):
    msg_template = "Unexpected error in {repo_cls}"


class UninitializedGroupError(RepositoryError):
    msg_tempalte = "{group} groups was never initialized"


class BaseDirectorError(CatalogBaseError):
    ...


class DirectorUnresponsiveError(BaseDirectorError):
    msg_template = "Director-v0 is not responsive"


class DirectorStatusError(BaseDirectorError):
    ...
