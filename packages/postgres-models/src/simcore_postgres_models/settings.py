# pylint: disable=unused-import
import os

from . import storage_tables, webserver_tables
from .tables.base import metadata

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
