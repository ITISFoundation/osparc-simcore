"""add uniqu constraint in licensed_items

Revision ID: e71ea59858f4
Revises: 4f31760a63ba
Create Date: 2025-01-30 18:42:15.192968+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "e71ea59858f4"
down_revision = "4f31760a63ba"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(
        "uq_licensed_resource_name_type",
        "licensed_items",
        ["licensed_resource_name", "licensed_resource_type"],
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "uq_licensed_resource_name_type", "licensed_items", type_="unique"
    )
    # ### end Alembic commands ###
