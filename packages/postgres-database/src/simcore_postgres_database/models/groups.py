""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""
import sqlalchemy as sa
from sqlalchemy.sql import func
from .base import metadata

# NOTE: using func.now() insted of python datetime ensure the time is computed server side
groups = sa.Table(
    "groups",
    metadata,
    sa.Column("gid", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=False),
    sa.Column("created", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
)

user_to_groups = sa.Table(
    "user_to_groups",
    metadata,
    sa.Column(
        "uid",
        sa.BigInteger,
        sa.ForeignKey(
            "users.id",
            name="fk_user_to_groups_id_users",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_user_to_groups_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column("created", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
    sa.UniqueConstraint("uid", "gid"),
)
