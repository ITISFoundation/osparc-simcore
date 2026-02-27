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


class _StepState(str, enum.Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    SUCCESS = "SUCCESS"
    CANCELLED = "CANCELLED"


ps_steps = sa.Table(
    f"{_COMMON_TABLE_PREFIX}_steps",
    metadata,
    sa.Column(
        "step_id",
        sa.BigInteger,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Unique identifier for the step",
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp when the step was created",
    ),
    sa.Column(
        "run_id",
        sa.BigInteger,
        sa.ForeignKey(
            f"{_COMMON_TABLE_PREFIX}_runs.run_id",
            name=f"fk_{_COMMON_TABLE_PREFIX}_steps_run_id_{_COMMON_TABLE_PREFIX}_runs",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Reference to the parent run",
    ),
    sa.Column(
        "step_type",
        sa.String,
        nullable=False,
        doc="Unique reference to the DAG node",
    ),
    sa.Column(
        "is_reverting",
        sa.Boolean,
        nullable=False,
        doc="Whether this step is a revert action",
    ),
    sa.Column(
        "timeout",
        sa.Interval,
        nullable=False,
        doc="Maximum duration allowed for the step to run",
    ),
    sa.Column(
        "available_attempts",
        sa.Integer,
        nullable=False,
        doc="Number of attempts remaining for the step",
    ),
    sa.Column(
        "attempt_number",
        sa.Integer,
        nullable=False,
        doc="Current attempt number",
    ),
    sa.Column(
        "state",
        sa.Enum(_StepState),
        nullable=False,
        doc="Current state of the step",
    ),
    sa.Column(
        "finished_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the step finished",
    ),
    sa.Column(
        "message",
        sa.String,
        nullable=True,
        doc="Optional message providing details about the step state",
    ),
    sa.UniqueConstraint(
        "run_id",
        "step_type",
        "is_reverting",
        name=f"uq_{_COMMON_TABLE_PREFIX}_steps_run_id_step_type_is_reverting",
    ),
)


ps_step_fail_history = sa.Table(
    f"{_COMMON_TABLE_PREFIX}_step_fail_history",
    metadata,
    sa.Column(
        "step_id",
        sa.BigInteger,
        sa.ForeignKey(
            f"{_COMMON_TABLE_PREFIX}_steps.step_id",
            name=f"fk_{_COMMON_TABLE_PREFIX}_step_fail_history_step_id_{_COMMON_TABLE_PREFIX}_steps",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Reference to the parent step",
    ),
    sa.Column(
        "attempt",
        sa.Integer,
        nullable=False,
        doc="Attempt number when the failure occurred",
    ),
    sa.Column(
        "state",
        sa.Enum(_StepState),
        nullable=False,
        doc="State of the step when the failure was recorded",
    ),
    sa.Column(
        "finished_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when the step attempt finished",
    ),
    sa.Column(
        "message",
        sa.String,
        nullable=False,
        doc="Error message or details about the failure",
    ),
    sa.PrimaryKeyConstraint(
        "step_id",
        "attempt",
        name=f"pk_{_COMMON_TABLE_PREFIX}_step_fail_history",
    ),
)


ps_step_lease = sa.Table(
    f"{_COMMON_TABLE_PREFIX}_step_lease",
    metadata,
    sa.Column(
        "step_id",
        sa.BigInteger,
        sa.ForeignKey(
            f"{_COMMON_TABLE_PREFIX}_steps.step_id",
            name=f"fk_{_COMMON_TABLE_PREFIX}_step_lease_step_id_{_COMMON_TABLE_PREFIX}_steps",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        primary_key=True,
        doc="Reference to the step being leased",
    ),
    sa.Column(
        "renew_count",
        sa.Integer,
        nullable=False,
        doc="Number of times the lease has been renewed",
    ),
    sa.Column(
        "owner",
        sa.String,
        nullable=False,
        doc="Identifier of the worker that owns the lease",
    ),
    sa.Column(
        "acquired_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp when the lease was first acquired",
    ),
    sa.Column(
        "last_heartbeat_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
        doc="Timestamp of the last heartbeat from the owner",
    ),
    sa.Column(
        "expires_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when the lease expires if not renewed",
    ),
)
