from . import metadata
from yarl import URL

# Schemas metadata (pre-loaded in __init__.py)
target_metadatas = [metadata, ]

def build_url(host, port, database, user=None, password=None) -> URL:
    """ postgresql+psycopg2://{user}:{password}@{host}:{port}/{database} """
    return URL.build(scheme="postgresql+psycopg2",
        user=user, password=password,
        host=host, port=port,
        path=f"/{database}")

__all__ = [
    'target_metadatas',
    'build_url'
]
