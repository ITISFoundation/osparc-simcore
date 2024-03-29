"""adds jinja template table

Revision ID: 33eafc1aa8ef
Revises: a8f0bacbbaef
Create Date: 2022-08-25 11:30:09.190686+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "33eafc1aa8ef"
down_revision = "a8f0bacbbaef"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "jinja2_templates",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "modified", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("name", name="jinja2_templates_name_pk"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("jinja2_templates")
    # ### end Alembic commands ###
