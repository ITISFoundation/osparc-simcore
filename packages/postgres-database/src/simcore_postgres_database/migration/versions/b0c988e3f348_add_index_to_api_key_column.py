"""add index to api_key column

Revision ID: b0c988e3f348
Revises: f65f7786cd4b
Create Date: 2025-03-13 08:53:05.722855+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b0c988e3f348"
down_revision = "f65f7786cd4b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f("ix_api_keys_api_key"), "api_keys", ["api_key"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_api_keys_api_key"), table_name="api_keys")
