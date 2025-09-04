"""Updates user roles with product support enum

Revision ID: 1546c76e03f0
Revises: 06eafd25d004
Create Date: 2025-09-04 17:58:46.902427+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "1546c76e03f0"
down_revision = "06eafd25d004"
branch_labels = None
depends_on = None


def upgrade():
    # Add the new PRODUCT_SUPPORT enum value to the existing UserRole enum
    op.execute("ALTER TYPE userrole ADD VALUE 'PRODUCT_SUPPORT'")


def downgrade():
    # Convert users with PRODUCT_SUPPORT role to TESTER before removing the enum value
    op.execute("UPDATE users SET role = 'TESTER' WHERE role = 'PRODUCT_SUPPORT'")

    # NOTE: Downgrade new updates requires re-building the entire enum!
    op.execute("ALTER TYPE userrole RENAME TO userrole_old")
    op.execute(
        "CREATE TYPE userrole AS ENUM('ANONYMOUS', 'GUEST', 'USER', 'TESTER', 'PRODUCT_OWNER', 'ADMIN')"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole USING "
        "role::text::userrole"
    )
    op.execute("DROP TYPE userrole_old")
