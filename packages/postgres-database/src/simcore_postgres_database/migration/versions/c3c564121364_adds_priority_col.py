"""Adds priority col

Revision ID: c3c564121364
Revises: 2ca532b0831f
Create Date: 2022-11-15 13:51:16.928575+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3c564121364"
down_revision = "2ca532b0831f"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "products",
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("products", "priority")
    # ### end Alembic commands ###
