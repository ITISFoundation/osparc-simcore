""" Services table

    - List of 3rd party services in the framework
    - Services have a key, tag, and access rights defined by group ids
"""

import sqlalchemy as sa

from sqlalchemy.sql import func, expression


from .base import metadata


# NOTE: using func.now() insted of python datetime ensure the time is computed server side
services = sa.Table(
    "services",
    metadata,
    sa.Column("key", sa.String, nullable=False),
    sa.Column("tag", sa.String, nullable=False),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_services_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "execute_access", sa.Boolean, nullable=False, server_default=expression.false()
    ),
    sa.Column("created", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
    sa.PrimaryKeyConstraint("key", "tag", "gid", name="services_pk"),
)
