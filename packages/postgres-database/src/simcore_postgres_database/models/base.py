""" Contains model's metadata

    - Collects all table's schemas
    - Metadata object needed to explicitly define table schemas
"""
from sqlalchemy.ext.declarative import declarative_base

#  DO NOT inheriting from _base. Use instead explicit table definitions
#  See https://docs.sqlalchemy.org/en/latest/orm/mapping_styles.html#classical-mappings
_base = declarative_base()
metadata = _base.metadata
