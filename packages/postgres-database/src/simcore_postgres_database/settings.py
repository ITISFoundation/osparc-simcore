from . import metadata
from .utils import build_url

# Schemas metadata (pre-loaded in __init__.py)
target_metadatas = [metadata, ]


__all__ = [
    'target_metadatas',
    'build_url'
]
