"""Adds ADMIN to userrole enum

Revision ID: c2d3acc313e1
Revises: 87a7b69f6723
Create Date: 2021-07-12 13:05:05.782876+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "c2d3acc313e1"
down_revision = "87a7b69f6723"
branch_labels = None
depends_on = None


# SEE https://medium.com/makimo-tech-blog/upgrading-postgresqls-enum-type-with-sqlalchemy-using-alembic-migration-881af1e30abe


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE userrole ADD VALUE 'ADMIN'")


def downgrade():
    # NOTE: Downgrade new updates requires re-building the entire enum!
    op.execute("ALTER TYPE userrole RENAME TO userrole_old")
    op.execute("CREATE TYPE userrole AS ENUM('ANONYMOUS', 'GUEST', 'USER', 'TESTER')")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole USING "
        "role::text::userrole"
    )
    op.execute("DROP TYPE userrole_old")
