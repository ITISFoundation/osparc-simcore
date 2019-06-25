import os

from . import metadata

# Schemas metadata (pre-loaded in __init__.py)
target_metadatas = [metadata, ]

# Data Source Name (DSN) template
DSN = "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

DEFAULT_POSTGRES_USER='simcore'
DEFAULT_POSTGRES_PASSWORD='simcore'
DEFAULT_POSTGRES_DB='simcoredb'
DEFAULT_POSTGRES_HOST='postgres'
DEFAULT_POSTGRES_PORT=5432

db_config = dict(
    user = os.getenv('POSTGRES_USER', DEFAULT_POSTGRES_USER),
    password = os.getenv('POSTGRES_PASSWORD', DEFAULT_POSTGRES_PASSWORD),
    host = os.getenv('POSTGRES_HOST', DEFAULT_POSTGRES_HOST),
    port = os.getenv('POSTGRES_PORT', DEFAULT_POSTGRES_PORT),
    database = os.getenv('POSTGRES_DB', DEFAULT_POSTGRES_DB)
)

sqlalchemy_url = DSN.format(**db_config)

__all__ = [
    'target_metadatas',
    'sqlalchemy_url',
    'DSN'
]
