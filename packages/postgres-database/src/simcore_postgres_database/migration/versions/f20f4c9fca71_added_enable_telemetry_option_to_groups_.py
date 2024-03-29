"""added enable telemetry option to groups extra properties

Revision ID: f20f4c9fca71
Revises: f9f9a650bf4b
Create Date: 2024-01-19 14:11:16.354169+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f20f4c9fca71"
down_revision = "f9f9a650bf4b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "groups_extra_properties",
        sa.Column(
            "enable_telemetry",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("groups_extra_properties", "enable_telemetry")
    # ### end Alembic commands ###
