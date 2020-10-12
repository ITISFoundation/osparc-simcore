"""add project running state

Revision ID: 009c81406676
Revises: d67672189ce1
Create Date: 2020-10-12 08:38:40.807576+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "009c81406676"
down_revision = "d67672189ce1"
branch_labels = None
depends_on = None


UNKNOWN = 0
PENDING = 1
RUNNING = 2
SUCCESS = 3
FAILED = 4

DB_PROCEDURE_NAME: str = "notify_comp_tasks_changed"
DB_TRIGGER_NAME: str = f"{DB_PROCEDURE_NAME}_event"


def upgrade():

    # create the new type
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
    # keep the old column for migration
    op.alter_column("comp_pipeline", "state", new_column_name="deprecated_state")
    op.alter_column("comp_tasks", "state", new_column_name="deprecated_state")
    # add the new columns
    op.add_column(
        "comp_pipeline",
        sa.Column(
            "state",
            sa.Enum(
                "NOT_STARTED",
                "PUBLISHED",
                "PENDING",
                "RUNNING",
                "SUCCESS",
                "FAILED",
                name="statetype",
            ),
            nullable=False,
            server_default="NOT_STARTED",
        ),
    )
    op.add_column(
        "comp_tasks",
        sa.Column(
            "state",
            sa.Enum(
                "NOT_STARTED",
                "PUBLISHED",
                "PENDING",
                "RUNNING",
                "SUCCESS",
                "FAILED",
                name="statetype",
            ),
            nullable=False,
            server_default="NOT_STARTED",
        ),
    )

    # migrate from deprecated state to state
    migration_map = {
        UNKNOWN: "NOT_STARTED",
        PENDING: "PENDING",
        RUNNING: "RUNNING",
        SUCCESS: "SUCCESS",
        FAILED: "FAILED",
    }
    [
        op.execute(
            sa.DDL(
                f"""
UPDATE comp_pipeline
SET state='{new}'
WHERE comp_pipeline.deprecated_state = '{old}'
"""
            )
        )
        for old, new in migration_map.items()
    ]
    [
        op.execute(
            sa.DDL(
                f"""
UPDATE comp_tasks
SET state='{new}'
WHERE comp_tasks.deprecated_state = '{old}'
"""
            )
        )
        for old, new in migration_map.items()
    ]

    # replace trigger to remove dependency on old state
    replace_trigger_query = sa.DDL(
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
    op.execute(replace_trigger_query)
    # remove the old columns
    op.drop_column("comp_tasks", "deprecated_state")
    op.drop_column("comp_pipeline", "deprecated_state")


def downgrade():
    # rename columns
    op.alter_column("comp_pipeline", "state", new_column_name="deprecated_state")
    op.alter_column("comp_tasks", "state", new_column_name="deprecated_state")
    # create the old columns again
    op.add_column("comp_pipeline", sa.Column("state", sa.String(), nullable=True))
    op.add_column("comp_tasks", sa.Column("state", sa.Integer(), nullable=True))
    # migrate the columns
    migration_map = {
        "NOT_STARTED": UNKNOWN,
        "PUBLISHED": UNKNOWN,
        "PENDING": PENDING,
        "RUNNING": RUNNING,
        "SUCCESS": SUCCESS,
        "FAILED": FAILED,
    }
    [
        op.execute(
            sa.DDL(
                f"""
UPDATE comp_pipeline
SET state='{new}'
WHERE comp_pipeline.deprecated_state = '{old}'
"""
            )
        )
        for old, new in migration_map.items()
    ]
    [
        op.execute(
            sa.DDL(
                f"""
UPDATE comp_tasks
SET state='{new}'
WHERE comp_tasks.deprecated_state = '{old}'
"""
            )
        )
        for old, new in migration_map.items()
    ]
    # replace trigger to remove dependency on old state
    replace_trigger_query = sa.DDL(
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
    op.execute(replace_trigger_query)
    # drop the columns
    op.drop_column("comp_tasks", "deprecated_state")
    op.drop_column("comp_pipeline", "deprecated_state")

    state_type = postgresql.ENUM(
        "NOT_STARTED",
        "PUBLISHED",
        "PENDING",
        "RUNNING",
        "SUCCESS",
        "FAILED",
        name="statetype",
    )
    state_type.drop(op.get_bind())
