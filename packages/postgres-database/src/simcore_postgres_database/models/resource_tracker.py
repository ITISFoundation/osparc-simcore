""" resource_tracker_container table

    - Table where we store the resource usage of each container that
    we scrape via resource-usage-tracker service
"""
import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_modified_datetime
from .base import metadata


class ContainerClassification(str, enum.Enum):
    DYNAMIC_SIDECAR = enum.auto()
    USER_SERVICE = enum.auto()


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
        "user_id",
        sa.BigInteger,
        nullable=False,
        doc="user_id label scraped via Prometheus (taken from container labels). We want to store the user id for tracking/billing purposes and be sure it stays there even when the user is deleted (that's also reason why we do not introduce foreign key)",
        index=True,
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        nullable=False,
        doc="project_uuid label scraped via Prometheus (taken from container labels). We want to store the project uuid for tracking/billing purposes and be sure it stays there even when the project is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "product_name",
        sa.String,
        nullable=False,
        doc="product_name label scraped via Prometheus (taken from container labels)",
        index=True,
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
        doc="node_uuid label scraped via Prometheus (taken from container labels). We want to store the node_uuid for tracking/billing purposes and be sure it stays there even when the node is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "node_label",
        sa.String,
        nullable=True,
        doc="we want to store the node/service label for tracking/billing purposes and be sure it stays there even when the node is deleted.",
    ),
    sa.Column(
        "instance",
        sa.String,
        nullable=True,
        doc="instance label scraped via Prometheus (taken from container labels, ex.: gpu1)",
    ),
    sa.Column(
        "project_name",
        sa.String,
        nullable=True,
        doc="we want to store the project name for tracking/billing purposes and be sure it stays there even when the project is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "user_email",
        sa.String,
        nullable=True,
        doc="we want to store the email for tracking/billing purposes and be sure it stays there even when the user is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Service Key (parsed from image label scraped via Prometheus)",
    ),
    sa.Column(
        "service_version",
        sa.String,
        nullable=False,
        doc="Service Version (parsed from image label scraped via Prometheus)",
    ),
    sa.Column(
        "cpu_limit",
        sa.Numeric(precision=3, scale=2),
        nullable=False,
        doc="CPU resource allocated to a container, ex.0.5 CPU shares",
    ),
    sa.Column(
        "memory_limit",
        sa.BigInteger,
        nullable=False,
        doc="memory limit in bytes scraped via Prometheus",
    ),
    sa.Column(
        "classification",
        sa.Enum(ContainerClassification),
        doc="Our custom classification of the container type",
    ),
    # ---------------------------
    sa.PrimaryKeyConstraint("container_id", name="resource_tracker_container_pkey"),
)
