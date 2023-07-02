""" resource_tracker_container table

    - Table where we store the resource usage of each container that
    we scrape via resource-usage-tracker service
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_modified_datetime
from .base import metadata

resource_tracker_container = sa.Table(
    "resource_tracker_container",
    metadata,
    sa.Column(
        "container_id",
        sa.String,
        nullable=False,
        doc="Refers to container id scraped via Prometheus",
    ),
    sa.Column(
        "image",
        sa.String,
        nullable=False,
        doc="image label scraped via Prometheus (taken from container labels), ex. registry.osparc.io/simcore/services/dynamic/jupyter-smash:3.0.9",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        nullable=False,
        doc="user_id label scraped via Prometheus (taken from container labels)",
        index=True,
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        nullable=False,
        doc="project_uuid label scraped via Prometheus (taken from container labels)",
    ),
    sa.Column(
        "product_name",
        sa.String,
        nullable=False,
        doc="product_name label scraped via Prometheus (taken from container labels)",
        index=True,
    ),
    sa.Column(
        "service_settings_reservation_nano_cpus",
        sa.BigInteger,
        nullable=True,
        doc="CPU resource allocated to a container, ex.500000000 means that the container is allocated 0.5 CPU shares",
    ),
    sa.Column(
        "service_settings_reservation_memory_bytes",
        sa.BigInteger,
        nullable=True,
        doc="memory limit in bytes scraped via Prometheus",
    ),
    sa.Column(
        "service_settings_reservation_additional_info",
        JSONB,
        nullable=False,
        doc="storing additional information about the reservation settings",
    ),
    sa.Column("container_cpu_usage_seconds_total", sa.Float, nullable=False),
    sa.Column(
        "prometheus_created",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="First container creation timestamp (UTC timestamp)",
    ),
    sa.Column(
        "prometheus_last_scraped",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Last prometheus scraped timestamp (UTC timestamp)",
        index=True,
    ),
    column_modified_datetime(timezone=True),
    sa.Column(
        "node_uuid",
        sa.String,
        nullable=False,
        doc="node_uuid label scraped via Prometheus (taken from container labels)",
    ),
    sa.Column(
        "node_label",
        sa.String,
        nullable=True,
        doc="node label",
    ),
    sa.Column(
        "instance",
        sa.String,
        nullable=True,
        doc="instance label scraped via Prometheus (taken from container labels)",
    ),
    sa.Column(
        "service_settings_limit_nano_cpus",
        sa.BigInteger,
        nullable=True,
        doc="CPU resource limit allocated to a container, ex.500000000 means that the container has limit for 0.5 CPU shares",
    ),
    sa.Column(
        "service_settings_limit_memory_bytes",
        sa.BigInteger,
        nullable=True,
        doc="memory limit in bytes scraped via Prometheus",
    ),
    sa.Column(
        "project_name",
        sa.String,
        nullable=True,
        doc="project name",
    ),
    sa.Column(
        "user_email",
        sa.String,
        nullable=True,
        doc="user email",
    ),
    # ---------------------------
    sa.PrimaryKeyConstraint("container_id", name="resource_tracker_container_pkey"),
)
