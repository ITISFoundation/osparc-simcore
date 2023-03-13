"""make key unique

Revision ID: 07dad1f604a4
Revises: ff33dcf20b44
Create Date: 2023-02-21 12:38:54.864295+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "07dad1f604a4"
down_revision = "ff33dcf20b44"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(
        "groups_extra_properties_group_id_key",
        "groups_extra_properties",
        type_="unique",
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(
        "groups_extra_properties_group_id_key", "groups_extra_properties", ["group_id"]
    )
    # ### end Alembic commands ###
