""" Facade for storage service (tables manager)

    - Facade to direct access to models in the database by
    the storage service
"""
from .tables.base import metadata
from .tables.file_meta_data_table import file_meta_data
from .tables.tokens_table import tokens

__all__ = [
    "tokens",
    "file_meta_data",
    "metadata"
]
