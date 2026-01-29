"""Dynamic services scheduler workflow tables

These tables back the durable orchestration engine implemented in the
`dynamic-scheduler` service (Postgres is the source of truth).

Naming notes:
- Tables are prefixed with `dynamic_services_scheduler_` to avoid collisions.
- IDs are stored as strings to remain compatible with existing simcore IDs.

"""

import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata


class DesiredState(enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class RunKind(enum.Enum):
    APPLY = "APPLY"
    TEARDOWN = "TEARDOWN"


class RunState(enum.Enum):
    APPLYING = "APPLYING"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    TEARING_DOWN = "TEARING_DOWN"
    SUCCEEDED = "SUCCEEDED"


class Direction(enum.Enum):
    DO = "DO"
    UNDO = "UNDO"


class StepState(enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    WAITING_MANUAL = "WAITING_MANUAL"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"


class ManualAction(enum.Enum):
    RETRY = "RETRY"
    SKIP = "SKIP"


dynamic_services_scheduler_nodes = sa.Table(
    "dynamic_services_scheduler_nodes",
    metadata,
    sa.Column(
        "node_id",
        sa.String,
        primary_key=True,
        doc="Node identifier (e.g. project node id). Stored as string for flexibility.",
    ),
    sa.Column(
        "desired_state",
        sa.Enum(DesiredState, name="dynamic_services_scheduler_desired_state"),
        nullable=False,
        doc="Desired steady state for the resource.",
    ),
    sa.Column(
        "desired_spec",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Desired specification for the APPLY run.",
    ),
    sa.Column(
        "desired_generation",
        sa.Integer,
        nullable=False,
        server_default=sa.text("0"),
        doc="Monotonically increasing generation; incremented on each desired_* change.",
    ),
    sa.Column(
        "active_run_id",
        sa.String,
        sa.ForeignKey(
            "dynamic_services_scheduler_runs.run_id",
            name="fk_dss_nodes_active_run_id_runs",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
        ),
        nullable=True,
        doc="Currently active run for this node (if any).",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Index("ix_dss_nodes_active_run_id", "active_run_id"),
)

register_modified_datetime_auto_update_trigger(dynamic_services_scheduler_nodes)


dynamic_services_scheduler_runs = sa.Table(
    "dynamic_services_scheduler_runs",
    metadata,
    sa.Column(
        "run_id",
        sa.String,
        primary_key=True,
        doc="Primary key; run identifier. Stored as string (uuid recommended).",
    ),
    sa.Column(
        "node_id",
        sa.String,
        sa.ForeignKey(
            dynamic_services_scheduler_nodes.c.node_id,
            name="fk_dss_runs_node_id_nodes",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Node this run applies to.",
    ),
    sa.Column(
        "generation",
        sa.Integer,
        nullable=False,
        doc="The node desired_generation targeted by this run.",
    ),
    sa.Column(
        "kind",
        sa.Enum(RunKind, name="dynamic_services_scheduler_run_kind"),
        nullable=False,
        doc="Whether this is an APPLY or TEARDOWN run.",
    ),
    sa.Column(
        "state",
        sa.Enum(RunState, name="dynamic_services_scheduler_run_state"),
        nullable=False,
        doc="Run state machine.",
    ),
    sa.Column(
        "cancel_requested_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Only meaningful for APPLY runs; signals cooperative cancellation.",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Index("ix_dss_runs_node_id_state", "node_id", "state"),
)

register_modified_datetime_auto_update_trigger(dynamic_services_scheduler_runs)


dynamic_services_scheduler_step_executions = sa.Table(
    "dynamic_services_scheduler_step_executions",
    metadata,
    sa.Column(
        "run_id",
        sa.String,
        sa.ForeignKey(
            dynamic_services_scheduler_runs.c.run_id,
            name="fk_dss_steps_run_id_runs",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        primary_key=True,
        doc="Run this step belongs to.",
    ),
    sa.Column(
        "step_id",
        sa.String,
        primary_key=True,
        doc="Stable step identifier within a workflow template.",
    ),
    sa.Column(
        "direction",
        sa.Enum(Direction, name="dynamic_services_scheduler_step_direction"),
        primary_key=True,
        doc="DO for forward execution, UNDO for compensation.",
    ),
    sa.Column(
        "state",
        sa.Enum(StepState, name="dynamic_services_scheduler_step_state"),
        nullable=False,
        doc="Step execution state machine.",
    ),
    sa.Column(
        "attempt",
        sa.Integer,
        nullable=False,
        server_default=sa.text("0"),
        doc="Attempt counter; increments on each new claim/execution.",
    ),
    sa.Column(
        "lease_until",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Lease expiry for the current worker claim.",
    ),
    sa.Column(
        "worker_id",
        sa.String,
        nullable=True,
        doc="Worker identifier holding the lease.",
    ),
    sa.Column(
        "last_error",
        sa.Text,
        nullable=True,
        doc="Last error string recorded for this step.",
    ),
    sa.Column(
        "manual_required_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="When manual intervention became required (WAITING_MANUAL).",
    ),
    sa.Column(
        "manual_action",
        sa.Enum(ManualAction, name="dynamic_services_scheduler_manual_action"),
        nullable=True,
        doc="Manual action applied (RETRY/SKIP).",
    ),
    sa.Column(
        "manual_action_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="When manual action was applied.",
    ),
    sa.Column(
        "manual_action_by",
        sa.String,
        nullable=True,
        doc="Who applied the manual action.",
    ),
    sa.Column(
        "manual_action_reason",
        sa.Text,
        nullable=True,
        doc="Mandatory reason for manual action.",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    # Hot path: `claim_one_step()` selects PENDING steps ordered by `modified`.
    # A partial index keeps this small and reduces write overhead on non-PENDING rows.
    sa.Index(
        "ix_dss_steps_pending_modified",
        "modified",
        postgresql_where=sa.text("state = 'PENDING'"),
    ),
    # Hot path: `recover_expired_running_steps()` selects RUNNING steps ordered by `lease_until`.
    # A partial index keeps this small and helps avoid scanning all step rows.
    sa.Index(
        "ix_dss_steps_running_lease_until",
        "lease_until",
        postgresql_where=sa.text("state = 'RUNNING' AND lease_until IS NOT NULL"),
    ),
    sa.Index(
        "ix_dss_steps_run_dir_state",
        "run_id",
        "direction",
        "state",
    ),
)

register_modified_datetime_auto_update_trigger(dynamic_services_scheduler_step_executions)


dynamic_services_scheduler_step_deps = sa.Table(
    "dynamic_services_scheduler_step_deps",
    metadata,
    sa.Column(
        "run_id",
        sa.String,
        sa.ForeignKey(
            dynamic_services_scheduler_runs.c.run_id,
            name="fk_dss_step_deps_run_id_runs",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        primary_key=True,
        doc="Run this dependency belongs to.",
    ),
    sa.Column(
        "direction",
        sa.Enum(Direction, name="dynamic_services_scheduler_step_direction"),
        primary_key=True,
        doc="DO/UNDO dependency graph for this run.",
    ),
    sa.Column(
        "step_id",
        sa.String,
        primary_key=True,
        doc="Dependent step.",
    ),
    sa.Column(
        "depends_on_step_id",
        sa.String,
        primary_key=True,
        doc="Prerequisite step.",
    ),
    sa.Index(
        "ix_dss_step_deps_lookup",
        "run_id",
        "direction",
        "step_id",
    ),
)
