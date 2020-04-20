""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""
from datetime import datetime

import sqlalchemy as sa

from .base import metadata


groups = sa.Table(
    "groups",
    metadata,
    sa.Column("gid", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=False),
    sa.Column("created", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    ),
)

user_to_groups = sa.Table(
    "user_to_groups",
    metadata,
    sa.Column(
        "uid",
        sa.BigInteger,
        sa.ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey("groups.gid", onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column("created", sa.DateTime(), nullable=False, default=datetime.utcnow),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    ),
    sa.UniqueConstraint("uid", "gid"),
)
