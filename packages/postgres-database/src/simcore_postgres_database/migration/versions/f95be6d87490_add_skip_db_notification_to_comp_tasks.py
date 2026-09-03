"""add skip_db_notification to comp_tasks

Revision ID: f95be6d87490
Revises: 9f24c8e1a3b7
Create Date: 2026-09-03 13:18:43.042091+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f95be6d87490"
down_revision = "9f24c8e1a3b7"
branch_labels = None
depends_on = None

DB_PROCEDURE_NAME: str = "notify_comp_tasks_changed"
DB_TRIGGER_NAME: str = f"{DB_PROCEDURE_NAME}_event"

_NEW_TRIGGER = sa.DDL(
    f"""
DROP TRIGGER IF EXISTS {DB_TRIGGER_NAME} on comp_tasks;
CREATE TRIGGER {DB_TRIGGER_NAME}
AFTER UPDATE OF outputs,state ON comp_tasks
    FOR EACH ROW
    WHEN (
        (OLD.outputs::jsonb IS DISTINCT FROM NEW.outputs::jsonb OR OLD.state IS DISTINCT FROM NEW.state)
        AND NEW.skip_db_notification IS NOT TRUE
    )
    EXECUTE PROCEDURE {DB_PROCEDURE_NAME}();
"""
)

_OLD_TRIGGER = sa.DDL(
    f"""
DROP TRIGGER IF EXISTS {DB_TRIGGER_NAME} on comp_tasks;
CREATE TRIGGER {DB_TRIGGER_NAME}
AFTER UPDATE OF outputs,state ON comp_tasks
    FOR EACH ROW
    WHEN ((OLD.outputs::jsonb IS DISTINCT FROM NEW.outputs::jsonb OR OLD.state IS DISTINCT FROM NEW.state))
    EXECUTE PROCEDURE {DB_PROCEDURE_NAME}();
"""
)


def upgrade():
    # NOTE: unrelated 'idx_conversation_messages_created_desc' auto-detected drift removed;
    # not part of this change (pre-existing model/migration mismatch, out of scope here)
    op.add_column(
        "comp_tasks",
        sa.Column(
            "skip_db_notification",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(_NEW_TRIGGER)


def downgrade():
    op.execute(_OLD_TRIGGER)
    op.drop_column("comp_tasks", "skip_db_notification")
