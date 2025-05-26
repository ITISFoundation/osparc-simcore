"""remove whole row in payload

Revision ID: 278daef7e99d
Revises: 4e7d8719855b
Create Date: 2025-05-22 21:22:11.084001+00:00

"""

from typing import Final

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "278daef7e99d"
down_revision = "4e7d8719855b"
branch_labels = None
depends_on = None

DB_PROCEDURE_NAME: Final[str] = "notify_comp_tasks_changed"
DB_TRIGGER_NAME: Final[str] = f"{DB_PROCEDURE_NAME}_event"
DB_CHANNEL_NAME: Final[str] = "comp_tasks_output_events"


def upgrade():
    drop_trigger = sa.DDL(
        f"""
DROP TRIGGER IF EXISTS {DB_TRIGGER_NAME} on comp_tasks;
"""
    )

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

        payload = json_build_object(
            'table', TG_TABLE_NAME,
            'changes', changes,
            'action', TG_OP,
            'task_id', record.task_id,
            'project_id', record.project_id,
            'node_id', record.node_id
        );

        PERFORM pg_notify('{DB_CHANNEL_NAME}', payload::text);

        RETURN NULL;
    END;
$$ LANGUAGE plpgsql;
"""
    )

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

    op.execute(drop_trigger)
    op.execute(task_output_changed_procedure)
    op.execute(task_output_changed_trigger)


def downgrade():
    drop_trigger = sa.DDL(
        f"""
DROP TRIGGER IF EXISTS {DB_TRIGGER_NAME} on comp_tasks;
"""
    )

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

    op.execute(drop_trigger)
    op.execute(task_output_changed_procedure)
    op.execute(task_output_changed_trigger)
