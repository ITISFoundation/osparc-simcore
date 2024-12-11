"""add cols to licensed_items_purchases table 2

Revision ID: d68b8128c23b
Revises: 8fa15c4c3977
Create Date: 2024-12-10 10:24:28.071216+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d68b8128c23b"
down_revision = "8fa15c4c3977"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("resource_tracker_licensed_items_purchases", "licensed_item_id")
    op.add_column(
        "resource_tracker_licensed_items_purchases",
        sa.Column("licensed_item_id", postgresql.UUID(as_uuid=True), nullable=False),
    )


def downgrade():
    ...
