"""Add fk for project_id to projects on file_meta_data table

Revision ID: d3e466e349d7
Revises: 75fc2513bb5c
Create Date: 2026-01-15 08:57:50.464622+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d3e466e349d7"
down_revision = "75fc2513bb5c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "DELETE FROM file_meta_data WHERE project_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM projects WHERE projects.uuid = file_meta_data.project_id)"
    )
    op.create_foreign_key(
        "fk_file_meta_data_project_id_projects",
        "file_meta_data",
        "projects",
        ["project_id"],
        ["uuid"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "fk_file_meta_data_project_id_projects",
        "file_meta_data",
        type_="foreignkey",
    )
