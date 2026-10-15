"""Restrict projects_nodes_changed trigger to specific columns

Revision ID: ae186e140a65
Revises: 966758d7226c
Create Date: 2026-10-15 12:58:00.000000+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ae186e140a65"
down_revision = "966758d7226c"
branch_labels = None
depends_on = None

# NOTE: Updates to these columns are user-visible changes to a node and must bump
# projects.last_change_date.
# UPDATE OF fires when a column appears in the UPDATE SET list, not only
# when its value actually changes.
_LAST_CHANGE_DATE_COLUMNS = (
    "boot_options",
    "input_access",
    "input_nodes",
    "inputs",
    "inputs_required",
    "inputs_units",
    "key",
    "label",
    "output",
    "required_resources",
    "run_hash",
    "state",
    "ui",
    "version",
)


def upgrade():
    op.execute(
        sa.DDL(
            f"""
DROP TRIGGER IF EXISTS projects_nodes_changed ON projects_nodes;
CREATE TRIGGER projects_nodes_changed
AFTER INSERT OR UPDATE OF {", ".join(_LAST_CHANGE_DATE_COLUMNS)} OR DELETE
ON projects_nodes
FOR EACH ROW
EXECUTE FUNCTION update_projects_last_change_date();
"""
        )
    )


def downgrade():
    op.execute(
        sa.DDL(
            """
DROP TRIGGER IF EXISTS projects_nodes_changed ON projects_nodes;
CREATE TRIGGER projects_nodes_changed
AFTER INSERT OR UPDATE OR DELETE
ON projects_nodes
FOR EACH ROW
EXECUTE FUNCTION update_projects_last_change_date();
"""
        )
    )
