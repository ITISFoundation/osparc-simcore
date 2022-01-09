from typing import Tuple

import pkg_resources

from . import storage_models, webserver_models
from .models.base import metadata

__version__: str = pkg_resources.get_distribution("simcore-postgres-database").version

__all__: Tuple[str, ...] = ("metadata", "webserver_models", "storage_models")
