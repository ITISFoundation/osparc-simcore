"""Scicrunch resources table

- Stores resources fetched from Scicrunch.
- Stores SOME of the information associated to Research Resource Identifiers (RRIDs) as defined in https://scicrunch.org/resources

Migration strategy:
- The primary key is `id`, which is unique and sufficient for migration.
- No foreign key dependencies exist.
- No additional changes are required; this table can be migrated as is.
"""

"""
"""

import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata

scicrunch_resources = sa.Table(
    "scicrunch_resources",
    metadata,
    sa.Column("rrid", sa.String, nullable=False, primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=True),
    sa.Column(
        "creation_date", sa.DateTime(), nullable=False, server_default=func.now()
    ),
    sa.Column(
        "last_change_date",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
)
