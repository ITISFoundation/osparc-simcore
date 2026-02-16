import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._common import RefActions
from .base import metadata

_COMMON_TABLE_PREFIX = "ps"


class _UserDesiredState(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


ps_user_requests = sa.Table(
    f"{_COMMON_TABLE_PREFIX}_user_requests",
    metadata,
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            name=f"fk_{_COMMON_TABLE_PREFIX}_user_requests_product_name_products",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Product associated with the request",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey(
            "users.id",
            name=f"fk_{_COMMON_TABLE_PREFIX}_user_requests_user_id_users",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="User who made the request",
    ),
    sa.Column(
        "project_id",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name=f"fk_{_COMMON_TABLE_PREFIX}_user_requests_project_id_projects",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Project associated with the request",
    ),
    sa.Column(
        "node_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        doc="Unique node identifier, only one request per node at any time",
    ),
    sa.Column(
        "requested_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp when the user made the request",
    ),
    sa.Column(
        "user_desired_state",
        sa.Enum(_UserDesiredState),
        nullable=False,
        doc="Desired state of the service: PRESENT (start) or ABSENT (stop)",
    ),
    sa.Column(
        "payload",
        JSONB,
        nullable=False,
        doc="Serialized DynamicServiceStart or DynamicServiceStop payload",
    ),
)


ps_runs = sa.Table(
    f"{_COMMON_TABLE_PREFIX}_runs",
    metadata,
    sa.Column(
        "run_id",
        sa.BigInteger,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Unique identifier for the run",
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp when the run was created",
    ),
    sa.Column(
        "node_id",
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        doc="Node identifier, only one active run per node at any time",
    ),
    sa.Column(
        "workflow_name",
        sa.String,
        nullable=False,
        doc="Reference to the workflow DAG being executed",
    ),
    sa.Column(
        "is_reverting",
        sa.Boolean,
        nullable=False,
        doc="Whether the run is reverting (rolling back) its actions",
    ),
    sa.Column(
        "waiting_manual_intervention",
        sa.Boolean,
        nullable=False,
        doc="Whether the run is waiting for manual intervention to proceed",
    ),
)


ps_run_store = sa.Table(
    f"{_COMMON_TABLE_PREFIX}_run_store",
    metadata,
    sa.Column(
        "run_id",
        sa.BigInteger,
        sa.ForeignKey(
            f"{_COMMON_TABLE_PREFIX}_runs.run_id",
            name=f"fk_{_COMMON_TABLE_PREFIX}_run_store_run_id_{_COMMON_TABLE_PREFIX}_runs",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Reference to the parent run",
    ),
    sa.Column(
        "key",
        sa.String,
        nullable=False,
        doc="Key identifier for the stored value",
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
        onupdate=sa.sql.func.now(),
        doc="Timestamp of the last update",
    ),
    sa.Column(
        "value",
        JSONB,
        nullable=False,
        doc="Stored value associated with the key",
    ),
    sa.PrimaryKeyConstraint("run_id", "key", name=f"pk_{_COMMON_TABLE_PREFIX}_run_store"),
)
