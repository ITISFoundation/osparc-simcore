"""resource_tracker_service_runs table"""

import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import NUMERIC_KWARGS, RefActions, column_modified_datetime
from .base import metadata
from .users import users


class ResourceTrackerServiceType(str, enum.Enum):
    COMPUTATIONAL_SERVICE = "COMPUTATIONAL_SERVICE"
    DYNAMIC_SERVICE = "DYNAMIC_SERVICE"


class ResourceTrackerServiceRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


resource_tracker_service_runs = sa.Table(
    "resource_tracker_service_runs",
    metadata,
    # Primary keys
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_service_runs_to_product_name",
        ),
        nullable=False,
        doc="Product name",
        primary_key=True,
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
        nullable=True,
        doc="We want to store the wallet id for tracking/billing purposes and be sure it stays there even when the wallet is deleted (that's also reason why we do not introduce foreign key)",
        index=True,
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
        nullable=True,
        doc="Pricing plan id for billing purposes",
    ),
    sa.Column(
        "pricing_unit_id",
        sa.BigInteger,
        nullable=True,
        doc="Pricing unit id for billing purposes",
    ),
    sa.Column(
        "pricing_unit_cost_id",
        sa.BigInteger,
        nullable=True,
        doc="Pricing unit cost id for billing purposes",
    ),
    sa.Column(
        "pricing_unit_cost",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=True,
        doc="Pricing unit cost used for billing purposes",
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
        sa.ForeignKey(
            users.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_service_runs_to_user_id",
        ),
        nullable=False,
        doc="We want to store the user id for tracking/billing purposes and be sure it stays there even when the user is deleted (that's also reason why we do not introduce foreign key)",
        index=True,
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
        nullable=False,
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
        nullable=False,
        doc="we want to store the node/service name/label for tracking/billing purposes and be sure it stays there even when the node is deleted.",
    ),
    # Project/Node parent fields
    sa.Column(
        "parent_project_id",  # UUID
        sa.String,
        nullable=False,
        doc="If a user starts computational jobs via a dynamic service, a new project is created in the backend. This newly created project is considered a child project, and the project from which it was created is the parent project. We want to store the parent project ID for tracking and billing purposes, and ensure it remains even when the node is deleted. This is also the reason why we do not introduce a foreign key.",
    ),
    sa.Column(
        "root_parent_project_id",  # UUID
        sa.String,
        nullable=False,
        doc="Similar to the parent project concept, we are flexible enough to allow multiple nested computational jobs, which create multiple nested projects. For this reason, we keep the parent project ID, so we know from which project the user started their computation.",
    ),
    sa.Column(
        "root_parent_project_name",
        sa.String,
        nullable=False,
        doc="We want to store the root parent project name for tracking/billing purposes.",
    ),
    sa.Column(
        "parent_node_id",  # UUID
        sa.String,
        nullable=False,
        doc="Since each project can have multiple nodes, similar to the parent project concept, we also store the parent node..",
    ),
    sa.Column(
        "root_parent_node_id",  # UUID
        sa.String,
        nullable=False,
        doc="Since each project can have multiple nodes, similar to the root parent project concept, we also store the root parent node.",
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
        default="'{}'::jsonb",
        doc="Service aresources, ex. cpu, gpu, memory, ...",
    ),
    sa.Column(
        "service_additional_metadata",
        JSONB,
        nullable=False,
        default="'{}'::jsonb",
        doc="Service additional metadata.",
    ),
    # Run timestamps
    sa.Column(
        "started_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when the service was started",
        index=True,
    ),
    sa.Column(
        "stopped_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the service was stopped",
    ),
    # Run status
    sa.Column(
        "service_run_status",  # Partial index was defined bellow
        sa.Enum(ResourceTrackerServiceRunStatus),
        nullable=False,
    ),
    column_modified_datetime(timezone=True),
    # Last Heartbeat
    sa.Column(
        "last_heartbeat_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when was the last heartbeat",
    ),
    sa.Column(
        "service_run_status_msg",
        sa.String,
        nullable=True,
        doc="Custom message/comment, for example to help understand root cause of the error during investigation",
    ),
    sa.Column(
        "missed_heartbeat_counter",
        sa.SmallInteger,
        nullable=False,
        default=0,
        doc="How many heartbeat checks have been missed",
    ),
)

# We define the partial index
sa.Index(
    "ix_resource_tracker_credit_transactions_status_running",
    resource_tracker_service_runs.c.service_run_status,
    postgresql_where=(
        resource_tracker_service_runs.c.service_run_status
        == ResourceTrackerServiceRunStatus.RUNNING
    ),
)
