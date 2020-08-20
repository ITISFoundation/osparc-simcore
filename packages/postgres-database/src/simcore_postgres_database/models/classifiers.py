""" Table to store the classifiers defined by every group

   In this initial version:
    - Every entry to the table is a set of classifiers associated to a group
    - The definitions of all classifiers as stored as a json in the 'bundle' column
    - Notice that the definition of classifier follows a
"""


import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .base import metadata

group_classifiers = sa.Table(
    "group_classifiers",
    metadata,
    sa.Column("id", sa.BigInteger, nullable=False),
    # TODO: add jsonschema validtion
    sa.Column("bundle", JSONB, nullable=False),
    sa.Column("created", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_group_classifiers_gid_to_groups_gid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        unique=True,  # Every Group can ONLY have one set of classifiers
    ),
    sa.PrimaryKeyConstraint("id", name="group_classifiers_pkey"),
)
