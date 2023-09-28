"""Updates user roles

Revision ID: 6e9f34338072
Revises: 7c552b906888
Create Date: 2023-09-26 12:29:23.376889+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "6e9f34338072"
down_revision = "7c552b906888"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE userrole ADD VALUE 'PRODUCT_OWNER'")


def downgrade():
    # NOTE: Downgrade new updates requires re-building the entire enum!
    op.execute("ALTER TYPE userrole RENAME TO userrole_old")
    op.execute(
        "CREATE TYPE userrole AS ENUM('ANONYMOUS', 'GUEST', 'USER', 'TESTER', 'ADMIN')"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole USING "
        "role::text::userrole"
    )
    op.execute("DROP TYPE userrole_old")
