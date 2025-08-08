"""Update project last_changed_date column when a node is created, updated or deleted.

Revision ID: c9c165644731
Revises: 201aa37f4d9a
Create Date: 2025-08-07 10:26:37.577990+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c9c165644731"
down_revision = "201aa37f4d9a"
branch_labels = None
depends_on = None


update_projects_last_change_date = sa.DDL(
    """
CREATE OR REPLACE FUNCTION update_projects_last_change_date()
RETURNS TRIGGER AS $$
DECLARE
    project_uuid VARCHAR;
BEGIN
    IF TG_OP = 'DELETE' THEN
        project_uuid := OLD.project_uuid;
    ELSE
        project_uuid := NEW.project_uuid;
    END IF;

    UPDATE projects
    SET last_change_date = NOW()
    WHERE uuid = project_uuid;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""
)


projects_nodes_changed = sa.DDL(
    """
DROP TRIGGER IF EXISTS projects_nodes_changed on projects_nodes;
CREATE TRIGGER projects_nodes_changed
AFTER INSERT OR UPDATE OR DELETE ON projects_nodes
FOR EACH ROW
EXECUTE FUNCTION update_projects_last_change_date();
"""
)


def upgrade():
    op.execute(update_projects_last_change_date)
    op.execute(projects_nodes_changed)


def downgrade():
    op.execute(
        sa.DDL("DROP TRIGGER IF EXISTS projects_nodes_changed ON projects_nodes;")
    )
    op.execute(sa.DDL("DROP FUNCTION IF EXISTS update_projects_last_change_date();"))
