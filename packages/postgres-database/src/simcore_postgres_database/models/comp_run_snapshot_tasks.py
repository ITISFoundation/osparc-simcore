"""Computational Tasks Table"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)
from .base import metadata
from .comp_pipeline import StateType
from .comp_runs import comp_runs

comp_run_snapshot_tasks = sa.Table(
    "comp_run_snapshot_tasks",
    metadata,
    sa.Column(
        "snapshot_task_id",
        sa.Integer,
        primary_key=True,
    ),
    sa.Column(
        "run_id",
        sa.Integer,
        sa.ForeignKey(
            comp_runs.c.run_id,
            name="fk_snapshot_tasks_to_comp_runs",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    sa.Column(
        "project_id",
        sa.String,
        doc="Project that contains the node associated to this task",
    ),
    sa.Column("node_id", sa.String, doc="Node associated to this task"),
    sa.Column(
        "node_class",
        ENUM(
            "COMPUTATIONAL",
            "INTERACTIVE",
            "FRONTEND",
            name="nodeclass",
            create_type=False,  # necessary to avoid alembic nodeclass already exists error
        ),
        doc="Classification of the node associated to this task",
    ),
    sa.Column("job_id", sa.String, doc="Worker job ID for this task"),
    sa.Column("internal_id", sa.Integer, doc="DEV: only for development. From 1 to N"),
    sa.Column("schema", sa.JSON, doc="Schema for inputs and outputs"),
    sa.Column("inputs", sa.JSON, doc="Input values"),
    sa.Column("outputs", sa.JSON, doc="Output values"),
    sa.Column(
        "run_hash",
        sa.String,
        nullable=True,
        doc="Hashes inputs before run. Used to detect changes in inputs.",
    ),
    sa.Column(
        "image", sa.JSON, doc="Metadata about service image associated to this node"
    ),
    sa.Column(
        "state",
        ENUM(
            "NOT_STARTED",
            "PUBLISHED",
            "PENDING",
            "RUNNING",
            "SUCCESS",
            "FAILED",
            "ABORTED",
            name="statetype",
            create_type=False,  # necessary to avoid alembic statetype already exists error
        ),
        nullable=False,
        server_default=StateType.NOT_STARTED.value,
        doc="Current state in the task lifecycle",
    ),
    sa.Column(
        "errors",
        postgresql.JSONB,
        nullable=True,
        doc="List[models_library.errors.ErrorDict] with error information"
        " for a failing state, otherwise set to None",
    ),
    sa.Column(
        "progress",
        sa.Numeric(precision=3, scale=2),  # numbers from 0.00 and 1.00
        nullable=True,
        doc="current progress of the task if available",
    ),
    sa.Column(
        "start", sa.DateTime(timezone=True), doc="UTC timestamp when task started"
    ),
    sa.Column(
        "end", sa.DateTime(timezone=True), doc="UTC timestamp for task completion"
    ),
    sa.Column(
        "last_heartbeat",
        sa.DateTime(timezone=True),
        doc="UTC timestamp for last task running check",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Column(
        "pricing_info",
        postgresql.JSONB,
        nullable=True,
        doc="Billing information of this task",
    ),
    sa.Column(
        "hardware_info",
        postgresql.JSONB,
        nullable=True,
        doc="Harware information of this task",
    ),
    # deprecated columns must be kept due to legacy services
    # utc timestamps for submission/start/end
    sa.Column(
        "submit",
        sa.DateTime(timezone=True),
        server_default=sa.text("'1900-01-01T00:00:00Z'::timestamptz"),
        doc="[DEPRECATED unused but kept for legacy services and must be filled with a default value of 1 January 1900]",
    ),
)
