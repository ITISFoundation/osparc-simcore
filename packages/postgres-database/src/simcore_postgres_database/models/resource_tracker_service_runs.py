""" resource_tracker_service_runs table

    - resource_usage_tracker is listening to rabbitmq events from director-v2 & sidecars and stores the data in this table
    - the point here is that ...

"""
import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import column_modified_datetime
from .base import metadata


class ResourceTrackerServiceType(str, enum.Enum):
    COMPUTATIONAL_SERVICE = "COMPUTATIONAL_SERVICE"
    DYNAMIC_SERVICE = "DYNAMIC_SERVICE"


class ResourceTrackerServiceRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    STOPPED_SUCCESS = "STOPPED_SUCCESS"
    STOPPED_USER_ERROR = "STOPPED_USER_ERROR"
    STOPPED_PLATFORM_ERROR = "STOPPED_PLATFORM_ERROR"


resource_tracker_service_runs = sa.Table(
    "resource_tracker_service_runs",
    metadata,
    # Primary keys
    sa.Column(
        "product_name", sa.String, nullable=False, doc="Product name", primary_key=True
    ),
    sa.Column(
        "service_run_id",
        sa.String,
        nullable=False,
        doc="Refers to the unique service_run_id provided by the director-v2/dynamic-sidecars.",
        primary_key=True,
    ),
    # Wallet fields
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        nullable=False,
        doc="We want to store the wallet id for tracking/billing purposes and be sure it stays there even when the wallet is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "wallet_name",
        sa.String,
        nullable=True,
        doc="We want to store the wallet name for tracking/billing purposes and be sure it stays there even when the wallet is deleted (that's also reason why we do not introduce foreign key)",
    ),
    # Pricing fields
    sa.Column(
        "pricing_plan_id",
        sa.BigInteger,
        nullable=False,
        doc="Pricing plan id for billing purposes",
    ),
    sa.Column(
        "pricing_detail_id",
        sa.BigInteger,
        nullable=False,
        doc="Pricing detail id for billing purposes",
    ),
    # User agent field
    sa.Column(
        "simcore_user_agent",
        sa.String,
        nullable=True,
        doc="Information about whether it is Puppeteer or not",
    ),
    # User fields
    sa.Column(
        "user_id",
        sa.BigInteger,
        nullable=False,
        doc="We want to store the user id for tracking/billing purposes and be sure it stays there even when the user is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "user_email",
        sa.String,
        nullable=True,
        doc="we want to store the email for tracking/billing purposes and be sure it stays there even when the user is deleted (that's also reason why we do not introduce foreign key)",
    ),
    # Project fields
    sa.Column(
        "project_id",  # UUID
        sa.String,
        nullable=False,
        doc="We want to store the project id for tracking/billing purposes and be sure it stays there even when the project is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "project_name",
        sa.String,
        nullable=True,
        doc="we want to store the project name for tracking/billing purposes and be sure it stays there even when the project is deleted (that's also reason why we do not introduce foreign key)",
    ),
    # Node fields
    sa.Column(
        "node_id",  # UUID
        sa.String,
        nullable=False,
        doc="We want to store the node id for tracking/billing purposes and be sure it stays there even when the node is deleted (that's also reason why we do not introduce foreign key)",
    ),
    sa.Column(
        "node_name",
        sa.String,
        nullable=True,
        doc="we want to store the node/service name/label for tracking/billing purposes and be sure it stays there even when the node is deleted.",
    ),
    # Service fields
    sa.Column(
        "service_key",
        sa.String,
        nullable=False,
        doc="Service Key",
    ),
    sa.Column(
        "service_version",
        sa.String,
        nullable=False,
        doc="Service Version",
    ),
    sa.Column(
        "service_type",
        sa.Enum(ResourceTrackerServiceType),
        nullable=False,
        doc="Service type, ex. COMPUTATIONAL, DYNAMIC",
    ),
    sa.Column(
        "service_resources",
        JSONB,
        nullable=False,
        server_default="{}",
        doc="Service aresources, ex. cpu, gpu, memory, ...",
    ),
    sa.Column(
        "service_additional_metadata",
        JSONB,
        nullable=False,
        server_default="{}",
        doc="Service additional metadata.",
    ),
    # Run timestamps
    sa.Column(
        "started_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when the service was started",
    ),
    sa.Column(
        "stopped_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when the service was stopped",
    ),
    # Run status
    sa.Column(
        "service_run_status",
        sa.Enum(ResourceTrackerServiceRunStatus),
        nullable=False,
    ),
    column_modified_datetime(timezone=True),
)
