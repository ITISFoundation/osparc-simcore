"""New dag table

Revision ID: 46c3cc232c0b
Revises: 31728148ab63
Create Date: 2020-02-20 16:59:35.564957+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '46c3cc232c0b'
down_revision = '31728148ab63'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('dags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(), nullable=True),
    sa.Column('version', sa.String(), nullable=True),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('contact', sa.String(), nullable=True),
    sa.Column('workbench', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dags_contact'), 'dags', ['contact'], unique=False)
    op.create_index(op.f('ix_dags_id'), 'dags', ['id'], unique=False)
    op.create_index(op.f('ix_dags_key'), 'dags', ['key'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_dags_key'), table_name='dags')
    op.drop_index(op.f('ix_dags_id'), table_name='dags')
    op.drop_index(op.f('ix_dags_contact'), table_name='dags')
    op.drop_table('dags')
    # ### end Alembic commands ###
