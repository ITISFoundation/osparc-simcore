"""add frontend_preferences_constraints to groups_extra_properties

Revision ID: 9f24c8e1a3b7
Revises: 3f8c0e8d11a4
Create Date: 2026-08-25 09:12:41.183920+00:00

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9f24c8e1a3b7"
down_revision = "3f8c0e8d11a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "groups_extra_properties",
        sa.Column(
            "frontend_preferences_constraints",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("groups_extra_properties", "frontend_preferences_constraints")
