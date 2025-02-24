"""enforce null

Revision ID: 163b11424cb1
Revises: a8d336ca9379
Create Date: 2025-02-24 12:44:10.538469+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "163b11424cb1"
down_revision = "a8d336ca9379"
branch_labels = None
depends_on = None


def upgrade():

    # SEE https://github.com/ITISFoundation/osparc-simcore/pull/7268

    op.execute(
        sa.DDL(
            """
        UPDATE services_meta_data
        SET thumbnail = NULL
        WHERE thumbnail = '';
        """
        )
    )
    op.execute(
        sa.DDL(
            """
        UPDATE services_meta_data
        SET version_display = NULL
        WHERE version_display = '';
        """
        )
    )
    op.execute(
        """
        UPDATE services_meta_data
        SET icon = NULL
        WHERE icon = '';
        """
    )


def downgrade():
    pass
