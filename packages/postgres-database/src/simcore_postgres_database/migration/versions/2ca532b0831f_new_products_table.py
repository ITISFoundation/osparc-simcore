"""new products table

Revision ID: 2ca532b0831f
Revises: 90c92dae8fc9
Create Date: 2022-11-11 10:54:13.921120+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2ca532b0831f"
down_revision = "90c92dae8fc9"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "products",
        sa.Column("vendor", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("manuals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("support", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.drop_column("products", "feedback_form_url")
    op.drop_column("products", "manual_extra_url")
    op.drop_column("products", "issues_new_url")
    op.drop_column("products", "manual_url")
    op.drop_column("products", "issues_login_url")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "products",
        sa.Column(
            "issues_login_url",
            sa.VARCHAR(),
            server_default=sa.text(
                "'https://github.com/ITISFoundation/osparc-simcore/issues'::character varying"
            ),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "manual_url",
            sa.VARCHAR(),
            server_default=sa.text(
                "'https://itisfoundation.github.io/osparc-manual/'::character varying"
            ),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "issues_new_url",
            sa.VARCHAR(),
            server_default=sa.text(
                "'https://github.com/ITISFoundation/osparc-simcore/issues/new'::character varying"
            ),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "manual_extra_url",
            sa.VARCHAR(),
            server_default=sa.text(
                "'https://itisfoundation.github.io/osparc-manual-z43/'::character varying"
            ),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "feedback_form_url", sa.VARCHAR(), autoincrement=False, nullable=True
        ),
    )
    op.drop_column("products", "support")
    op.drop_column("products", "manuals")
    op.drop_column("products", "issues")
    op.drop_column("products", "vendor")
    # ### end Alembic commands ###
