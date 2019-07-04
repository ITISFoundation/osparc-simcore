""" Facade for storage service (tables manager)

    - Facade to direct access to models in the database by
    the storage service
"""
from .models.base import metadata
from .models.file_meta_data import file_meta_data
from .models.tokens import tokens

__all__ = [
    "tokens",
    "file_meta_data",
    "metadata"
]
