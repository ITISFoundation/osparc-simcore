"""Remove projects.access_rights column

Revision ID: 9c8488e82582
Revises: 2962a102c124
Create Date: 2026-07-08 13:01:34.117651+00:00

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9c8488e82582"
down_revision = "2962a102c124"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("projects", "access_rights")


def downgrade():
    op.add_column(
        "projects",
        sa.Column(
            "access_rights",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            autoincrement=False,
            nullable=False,
        ),
    )
