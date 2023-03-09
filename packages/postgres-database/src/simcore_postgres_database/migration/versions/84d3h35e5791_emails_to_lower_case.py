"""blackfynn to pennsieve

Revision ID: 84d3h35e5791
Revises: 07dad1f604a4
Create Date: 2023-03-09 07:59:54.814215+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "84d3h35e5791"
down_revision = "07dad1f604a4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.DDL("UPDATE users SET email=lower(email)"))


def downgrade():
    pass
