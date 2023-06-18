""" resource_tracker_container table

    - Table where we store the resource usage of each container that
    we scrape via resource-usage-tracker service
"""

import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata

resource_tracker_container = sa.Table(
    "resource_tracker_container",
    metadata,
    sa.Column(
        "id",  # container_id
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "image",
        sa.String,
        nullable=False,
        doc="ex. registry.osparc.io/simcore/services/dynamic/jupyter-smash:3.0.9",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        nullable=False,
    ),
    sa.Column(
        "product_name",
        sa.String,
        nullable=False,
    ),
    sa.Column("cpu_reservation", sa.BigInteger, nullable=False),
    sa.Column("ram_reservation", sa.BigInteger, nullable=False),
    sa.Column("container_cpu_usage_seconds_total", sa.Float, nullable=False),
    sa.Column(
        "created_timestamp",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="First container creation timestamp (UTC timestamp)",
    ),
    sa.Column(
        "last_prometheus_scraped_timestamp",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Last prometheus scraped timestamp (UTC timestamp)",
    ),
    sa.Column(
        "last_row_updated_timestamp",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Last row updated timestamp (UTC timestamp)",
    ),
    # ---------------------------
    sa.PrimaryKeyConstraint("id", name="resource_tracker_container_pkey"),
)
