from . import metadata

# Schemas metadata (pre-loaded in __init__.py)
target_metadatas = [metadata, ]

# Data Source Name (DSN) template
DSN = "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

__all__ = [
    'target_metadatas',
    'DSN'
]
