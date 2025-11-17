"""rename tags_to_groups

Revision ID: feca36c8e18f
Revises: e8057a4a7bb0
Create Date: 2024-08-23 12:30:56.650085+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "feca36c8e18f"
down_revision = "e8057a4a7bb0"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("tags_to_groups", "tags_access_rights")


def downgrade():
    # Reverse the table rename from projects_tags to study_tags
    op.rename_table("tags_access_rights", "tags_to_groups")
