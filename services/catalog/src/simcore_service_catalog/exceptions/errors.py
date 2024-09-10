from typing import Any

from models_library.errors_classes import OsparcErrorMixin
from simcore_service_webserver.catalog.exceptions import BaseCatalogError


class CatalogBaseError(OsparcErrorMixin, Exception):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)


class RepositoryError(CatalogBaseError):
    msg_template = "Unexpected error in {repo_cls}"


class UninitializedGroupError(RepositoryError):
    msg_tempalte = "{group} groups was never initialized"


class BaseDirectorError(BaseCatalogError):
    ...


class DirectorUnresponsiveError(BaseDirectorError):
    msg_template = "Director-v0 is not responsive"


class DirectorStatusError(BaseDirectorError):
    ...
