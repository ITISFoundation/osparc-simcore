"""add task run hash

Revision ID: ee62bf5e40b9
Revises: 65198ad31f29
Create Date: 2021-01-15 18:25:42.016784+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ee62bf5e40b9'
down_revision = '65198ad31f29'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comp_tasks', sa.Column('run_hash', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comp_tasks', 'run_hash')
    # ### end Alembic commands ###
