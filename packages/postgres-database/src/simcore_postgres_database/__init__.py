from importlib.metadata import version

from . import storage_models, webserver_models
from .models.base import metadata

__version__: str = version("simcore-postgres-database")

__all__: tuple[str, ...] = (
    "metadata",
    "webserver_models",
    "storage_models",
)

# nopycln: file
