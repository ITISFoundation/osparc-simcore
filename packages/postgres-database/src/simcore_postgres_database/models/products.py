""" Prodcuts table

    - List of products served by the simcore platform
    - Products have a name, url(s), frontend
"""

import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata

# NOTE: using func.now() instead of python datetime ensure the time is computed server side


products = sa.Table(
    "products",
    metadata,
    sa.Column("name", sa.String, nullable=False),
    sa.Column("host_regex", sa.String, nullable=False),
    sa.Column("frontend", sa.String, nullable=True),
    sa.Column("created", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
    sa.PrimaryKeyConstraint("name", name="products_pk"),
)
