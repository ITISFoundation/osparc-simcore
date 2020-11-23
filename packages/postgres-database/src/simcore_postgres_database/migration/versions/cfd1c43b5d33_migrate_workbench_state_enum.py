"""migrate workbench state enum

Revision ID: cfd1c43b5d33
Revises: c8a7073deebb
Create Date: 2020-11-17 16:42:32.511722+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cfd1c43b5d33'
down_revision = 'c8a7073deebb'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.DDL(
        """
UPDATE projects
    SET workbench = (regexp_replace(workbench::text, '"FAILURE"', '"FAILED"'))::json
    WHERE workbench::text LIKE '%%FAILURE%%'
        """
        )
    )


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
