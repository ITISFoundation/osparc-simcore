"""new account_request_status column

Revision ID: de44e42e2e3b
Revises: 742123f0933a
Create Date: 2025-04-24 07:27:20.753638+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "de44e42e2e3b"
down_revision = "742123f0933a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users_pre_registration_details",
        sa.Column(
            "account_request_status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="accountrequeststatus"),
            server_default=sa.text("'PENDING'::account_request_status"),
            nullable=False,
        ),
    )


def downgrade():
    op.create_index(
        "idx_projects_last_change_date_desc",
        "projects",
        [sa.text("last_change_date DESC")],
        unique=False,
    )
