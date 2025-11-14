"""Contains model's metadata

- Collects all table's schemas
- Metadata object needed to explicitly define table schemas
"""

from typing import cast

import sqlalchemy.orm
from sqlalchemy.ext.declarative import DeclarativeMeta

#  DO NOT inheriting from _base. Use instead explicit table definitions
#  See https://docs.sqlalchemy.org/en/latest/orm/mapping_styles.html#classical-mappings
Base = cast(DeclarativeMeta, sqlalchemy.orm.declarative_base())

metadata = Base.metadata
