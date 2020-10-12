""" Computational Tasks Table

"""
import enum

import sqlalchemy as sa

from .base import metadata
from .comp_pipeline import StateType


class NodeClass(enum.Enum):
    COMPUTATIONAL = "COMPUTATIONAL"
    INTERACTIVE = "INTERACTIVE"
    FRONTEND = "FRONTEND"


comp_tasks = sa.Table(
    "comp_tasks",
    metadata,
    # this task db id
    sa.Column("task_id", sa.Integer, primary_key=True),
    sa.Column("project_id", sa.String, sa.ForeignKey("comp_pipeline.project_id")),
    # dag node id and class
    sa.Column("node_id", sa.String),
    sa.Column("node_class", sa.Enum(NodeClass)),
    # celery task id
    sa.Column("job_id", sa.String),
    # internal id (better for debugging, nodes from 1 to N)
    sa.Column("internal_id", sa.Integer),
    sa.Column("schema", sa.JSON),
    sa.Column("inputs", sa.JSON),
    sa.Column("outputs", sa.JSON),
    sa.Column("image", sa.JSON),
    sa.Column(
        "state", sa.Enum(StateType), nullable=False, server_default=StateType.NOT_STARTED.value
    ),
    # utc timestamps for submission/start/end
    sa.Column("submit", sa.DateTime),
    sa.Column("start", sa.DateTime),
    sa.Column("end", sa.DateTime),
    sa.UniqueConstraint("project_id", "node_id", name="project_node_uniqueness"),
)


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
    WHEN ((OLD.outputs::jsonb IS DISTINCT FROM NEW.outputs::jsonb OR OLD.state IS DISTINCT FROM NEW.state)
        AND NEW.node_class <> 'FRONTEND')
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
    BEGIN
        IF (TG_OP = 'DELETE') THEN
            record = OLD;
        ELSE
            record = NEW;
        END IF;

        payload = json_build_object('table', TG_TABLE_NAME,
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
