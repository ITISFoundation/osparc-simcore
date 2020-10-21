"""add aborted state

Revision ID: 64e91497d257
Revises: 009c81406676
Create Date: 2020-10-14 20:05:26.968038+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "64e91497d257"
down_revision = "27c6a30d7c24"
branch_labels = None
depends_on = None

DB_PROCEDURE_NAME: str = "notify_comp_tasks_changed"
DB_TRIGGER_NAME: str = f"{DB_PROCEDURE_NAME}_event"


def upgrade():
    # change current name of enum
    op.execute(
        sa.DDL(
            """
ALTER TYPE statetype RENAME TO statetype_old;
    """
        )
    )
    # create the new statetype with ABORTED
    state_type = postgresql.ENUM(
        "NOT_STARTED",
        "PUBLISHED",
        "PENDING",
        "RUNNING",
        "SUCCESS",
        "FAILED",
        "ABORTED",
        name="statetype",
    )
    state_type.create(op.get_bind())

    # update all the columns, trigger depending on it and drop the old type
    op.execute(
        sa.DDL(
            f"""
DROP TRIGGER IF EXISTS {DB_TRIGGER_NAME} on comp_tasks;
ALTER TABLE comp_tasks ALTER COLUMN state DROP DEFAULT;
ALTER TABLE comp_tasks ALTER COLUMN state TYPE statetype USING state::text::statetype;
ALTER TABLE comp_tasks ALTER COLUMN state SET DEFAULT 'NOT_STARTED';

ALTER TABLE comp_pipeline ALTER COLUMN state DROP DEFAULT;
ALTER TABLE comp_pipeline ALTER COLUMN state TYPE statetype USING state::text::statetype;
ALTER TABLE comp_pipeline ALTER COLUMN state SET DEFAULT 'NOT_STARTED';
DROP TYPE statetype_old;
    """
        )
    )
    op.execute(
        sa.DDL(
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
    )


def downgrade():
    # set the ABORTED value to NOT_STARTED and rename the statetype
    op.execute(
        sa.DDL(
            """
UPDATE comp_tasks SET state = 'NOT_STARTED' WHERE state = 'ABORTED';
UPDATE comp_pipeline SET state = 'NOT_STARTED' WHERE state = 'ABORTED';
ALTER TYPE statetype RENAME TO statetype_old;
    """
        )
    )
    # create the statetype
    state_type = postgresql.ENUM(
        "NOT_STARTED",
        "PUBLISHED",
        "PENDING",
        "RUNNING",
        "SUCCESS",
        "FAILED",
        name="statetype",
    )
    state_type.create(op.get_bind())
    # update all the columns, trigger depending on it
    op.execute(
        sa.DDL(
            f"""
DROP TRIGGER IF EXISTS {DB_TRIGGER_NAME} on comp_tasks;
ALTER TABLE comp_tasks ALTER COLUMN state DROP DEFAULT;
ALTER TABLE comp_tasks ALTER COLUMN state TYPE statetype USING state::text::statetype;
ALTER TABLE comp_tasks ALTER COLUMN state SET DEFAULT 'NOT_STARTED';

ALTER TABLE comp_pipeline ALTER COLUMN state DROP DEFAULT;
ALTER TABLE comp_pipeline ALTER COLUMN state TYPE statetype USING state::text::statetype;
ALTER TABLE comp_pipeline ALTER COLUMN state SET DEFAULT 'NOT_STARTED';
DROP TYPE statetype_old;
    """
        )
    )
    op.execute(
        sa.DDL(
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
    )
