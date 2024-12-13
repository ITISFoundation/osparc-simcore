"""modify licenses DB

Revision ID: 3720518f82a7
Revises: 77ac824a77ff
Create Date: 2024-12-13 12:46:38.302027+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3720518f82a7"
down_revision = "77ac824a77ff"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("resource_tracker_licensed_items_usage", "licensed_item_id")
    op.add_column(
        "resource_tracker_licensed_items_usage",
        sa.Column("licensed_item_id", postgresql.UUID(as_uuid=True), nullable=False),
    )


def downgrade():
    ...
