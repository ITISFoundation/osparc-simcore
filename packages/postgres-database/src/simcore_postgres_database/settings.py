import os

from . import metadata

# Schemas metadata (pre-loaded in __init__.py)
target_metadatas = [metadata, ]

# Data Source Name (DSN) template
DSN = "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

sqlalchemy_url = DSN.format(
    user = os.getenv('POSTGRES_USER'),
    password = os.getenv('POSTGRES_PASSWORD'),
    host = os.getenv('POSTGRES_HOST'),
    port = os.getenv('POSTGRES_PORT'),
    database = os.getenv('POSTGRES_DB')
)

__all__ = [
    'target_metadatas',
    'sqlalchemy_url',
    'DSN'
]
