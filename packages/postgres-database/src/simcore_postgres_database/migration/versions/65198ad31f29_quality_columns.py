"""add quality to projects and services

Revision ID: 65198ad31f29
Revises: b60363fe438f
Create Date: 2021-01-05 14:09:26.552123+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "65198ad31f29"
down_revision = "b60363fe438f"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "projects",
        sa.Column(
            "quality",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column(
        'services_meta_data',
        'metadata',
        new_column_name='quality'
    )
    # ### end Alembic commands ###



def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("projects", "quality")
    op.alter_column(
        'services_meta_data',
        'quality',
        new_column_name='metadata'
    )
    # ### end Alembic commands ###
