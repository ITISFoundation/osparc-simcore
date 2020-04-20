""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""
from datetime import datetime

import sqlalchemy as sa

from .base import metadata


groups = sa.Table(
    "users",
    metadata,
    sa.Column("gid", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("users", sa.ARRAY(sa.ForeignKey("users.id")), nullable=False),
    sa.Column("created", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    ),
)
