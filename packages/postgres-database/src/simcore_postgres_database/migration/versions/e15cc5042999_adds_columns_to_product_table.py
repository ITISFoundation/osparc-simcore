"""adds columns to product table

Revision ID: e15cc5042999
Revises: c6185fba2720
Create Date: 2022-08-19 15:01:49.326429+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e15cc5042999"
down_revision = "c6185fba2720"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column(
            "display_name", sa.String(), server_default="o²S²PARC", nullable=False
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "support_email",
            sa.String(),
            server_default="support@osparc.io",
            nullable=False,
        ),
    )
    op.add_column(
        "products", sa.Column("twilio_messaging_sid", sa.String(), nullable=True)
    )
    op.add_column(
        "products",
        sa.Column(
            "manual_url",
            sa.String(),
            server_default="https://itisfoundation.github.io/osparc-manual/",
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "manual_extra_url",
            sa.String(),
            server_default="https://itisfoundation.github.io/osparc-manual-z43/",
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "issues_login_url",
            sa.String(),
            server_default="https://github.com/ITISFoundation/osparc-simcore/issues",
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "issues_new_url",
            sa.String(),
            server_default="https://github.com/ITISFoundation/osparc-simcore/issues/new",
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "feedback_form_url",
            sa.String(),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("products", "feedback_form_url")
    op.drop_column("products", "issues_new_url")
    op.drop_column("products", "issues_login_url")
    op.drop_column("products", "manual_extra_url")
    op.drop_column("products", "manual_url")
    op.drop_column("products", "twilio_messaging_sid")
    op.drop_column("products", "support_email")
    op.drop_column("products", "display_name")
