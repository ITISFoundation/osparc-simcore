"""renamed study_tags table

Revision ID: 7604e65e2f83
Revises: 617e0ecaf602
Create Date: 2024-08-23 12:03:59.328670+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7604e65e2f83"
down_revision = "617e0ecaf602"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("study_tags", "projects_tags")

    # Rename the column from study_id to project_id in the renamed table
    op.alter_column("projects_tags", "study_id", new_column_name="project_id")


def downgrade():
    # Reverse the column rename from project_id to study_id
    op.alter_column("projects_tags", "project_id", new_column_name="study_id")

    # Reverse the table rename from projects_tags to study_tags
    op.rename_table("projects_tags", "study_tags")
