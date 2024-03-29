"""phone not-unique

Revision ID: 30e8b752e33e
Revises: c1d0e98cd289
Create Date: 2024-03-11 12:21:35.856004+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "30e8b752e33e"
down_revision = "c1d0e98cd289"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("user_phone_unique_constraint", "users", type_="unique")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint("user_phone_unique_constraint", "users", ["phone"])
    # ### end Alembic commands ###
