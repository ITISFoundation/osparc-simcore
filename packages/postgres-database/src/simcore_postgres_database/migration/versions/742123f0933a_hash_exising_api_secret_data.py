"""hash exising api_secret data

Revision ID: 742123f0933a
Revises: b0c988e3f348
Create Date: 2025-03-13 09:39:43.895529+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "742123f0933a"
down_revision = "b0c988e3f348"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE api_keys
        SET api_secret = crypt(api_secret, gen_salt('bf', 10))
        """
    )


def downgrade():
    pass
