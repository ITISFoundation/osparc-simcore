from importlib.metadata import version

from . import storage_models, webserver_models
from .models.base import metadata

__version__: str = version("simcore-postgres-database")

__all__: tuple[str, ...] = (
    "metadata",
    "storage_models",
    "webserver_models",
)

# nopycln: file
