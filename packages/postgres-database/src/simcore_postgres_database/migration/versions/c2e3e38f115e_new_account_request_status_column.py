"""new account_request_status column

Revision ID: c2e3e38f115e
Revises: 742123f0933a
Create Date: 2025-04-24 07:29:42.530145+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c2e3e38f115e"
down_revision = "742123f0933a"
branch_labels = None
depends_on = None


def upgrade():
    # Create the enum type first
    account_request_status = sa.Enum(
        "PENDING", "APPROVED", "REJECTED", name="accountrequeststatus"
    )
    account_request_status.create(op.get_bind())

    # Reuse the enum in the column definition
    op.add_column(
        "users_pre_registration_details",
        sa.Column(
            "account_request_status",
            account_request_status,
            server_default=sa.text("'PENDING'::accountrequeststatus"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("users_pre_registration_details", "account_request_status")

    # Drop the enum type after dropping the column
    sa.Enum(name="accountrequeststatus").drop(op.get_bind())
