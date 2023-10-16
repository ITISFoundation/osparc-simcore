import pkg_resources

from . import storage_models, webserver_models
from .models.base import metadata

__version__: str = pkg_resources.get_distribution("simcore-postgres-database").version

__all__: tuple[str, ...] = ("metadata", "webserver_models", "storage_models")

# nopycln: file
