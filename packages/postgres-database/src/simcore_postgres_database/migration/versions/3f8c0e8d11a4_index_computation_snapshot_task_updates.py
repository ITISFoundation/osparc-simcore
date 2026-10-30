"""index computation snapshot task updates

Revision ID: 3f8c0e8d11a4
Revises: 0e7558d0499c
Create Date: 2026-08-14 09:26:52.256875+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "3f8c0e8d11a4"
down_revision = "0e7558d0499c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_comp_run_snapshot_tasks_run_id_node_id", "comp_run_snapshot_tasks", ["run_id", "node_id"], unique=False
    )


def downgrade():
    op.drop_index("ix_comp_run_snapshot_tasks_run_id_node_id", table_name="comp_run_snapshot_tasks")
