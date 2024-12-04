""" Computational Tasks Table

"""

import enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .comp_pipeline import StateType


class NodeClass(enum.Enum):
    COMPUTATIONAL = "COMPUTATIONAL"
    INTERACTIVE = "INTERACTIVE"
    FRONTEND = "FRONTEND"


comp_tasks = sa.Table(
    "comp_tasks",
    metadata,
    sa.Column(
        "task_id",
        sa.Integer,
        primary_key=True,
        doc="Primary key, identifies the task in this table",
    ),
    sa.Column(
        "project_id",
        sa.String,
        sa.ForeignKey("comp_pipeline.project_id"),
        doc="Project that contains the node associated to this task",
    ),
    sa.Column("node_id", sa.String, doc="Node associated to this task"),
    sa.Column(
        "node_class",
        sa.Enum(NodeClass),
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
        sa.Enum(StateType),
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
    # utc timestamps for submission/start/end
    sa.Column(
        "submit", sa.DateTime(timezone=True), doc="UTC timestamp for task submission"
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
    # ------
    sa.UniqueConstraint("project_id", "node_id", name="project_node_uniqueness"),
)

register_modified_datetime_auto_update_trigger(comp_tasks)

DB_PROCEDURE_NAME: str = "notify_comp_tasks_changed"
DB_TRIGGER_NAME: str = f"{DB_PROCEDURE_NAME}_event"
DB_CHANNEL_NAME: str = "comp_tasks_output_events"

# ------------------------ TRIGGERS

task_output_changed_trigger = sa.DDL(
    f"""
DROP TRIGGER IF EXISTS {DB_TRIGGER_NAME} on comp_tasks;
CREATE TRIGGER {DB_TRIGGER_NAME}
AFTER UPDATE OF outputs,state ON comp_tasks
    FOR EACH ROW
    WHEN ((OLD.outputs::jsonb IS DISTINCT FROM NEW.outputs::jsonb OR OLD.state IS DISTINCT FROM NEW.state))
    EXECUTE PROCEDURE {DB_PROCEDURE_NAME}();
"""
)


# ---------------------- PROCEDURES
task_output_changed_procedure = sa.DDL(
    f"""
CREATE OR REPLACE FUNCTION {DB_PROCEDURE_NAME}() RETURNS TRIGGER AS $$
    DECLARE
        record RECORD;
        payload JSON;
        changes JSONB;
    BEGIN
        IF (TG_OP = 'DELETE') THEN
            record = OLD;
        ELSE
            record = NEW;
        END IF;

        SELECT jsonb_agg(pre.key ORDER BY pre.key) INTO changes
        FROM jsonb_each(to_jsonb(OLD)) AS pre, jsonb_each(to_jsonb(NEW)) AS post
        WHERE pre.key = post.key AND pre.value IS DISTINCT FROM post.value;

        payload = json_build_object('table', TG_TABLE_NAME,
                                    'changes', changes,
                                    'action', TG_OP,
                                    'data', row_to_json(record));

        PERFORM pg_notify('{DB_CHANNEL_NAME}', payload::text);

        RETURN NULL;
    END;
$$ LANGUAGE plpgsql;
"""
)

sa.event.listen(comp_tasks, "after_create", task_output_changed_procedure)
sa.event.listen(
    comp_tasks,
    "after_create",
    task_output_changed_trigger,
)
