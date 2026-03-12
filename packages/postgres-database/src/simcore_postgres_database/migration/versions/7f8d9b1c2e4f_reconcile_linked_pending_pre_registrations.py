"""Reconcile linked pending pre-registrations

Revision ID: 7f8d9b1c2e4f
Revises: 4c8dcaac4285
Create Date: 2026-03-12 17:30:00.000000+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7f8d9b1c2e4f"
down_revision = "4c8dcaac4285"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE users_pre_registration_details
            SET
                account_request_status = 'APPROVED'::accountrequeststatus,
                account_request_reviewed_by = COALESCE(account_request_reviewed_by, created_by),
                account_request_reviewed_at = COALESCE(account_request_reviewed_at, NOW())
            WHERE
                user_id IS NOT NULL
                AND account_request_status = 'PENDING'::accountrequeststatus
                AND EXISTS (
                    SELECT 1
                    FROM user_to_groups
                    JOIN products ON products.group_id = user_to_groups.gid
                    WHERE
                        user_to_groups.uid = users_pre_registration_details.user_id
                        AND products.name = users_pre_registration_details.product_name
                )
            """
        )
    )


def downgrade():
    """Data migration is intentionally not reversed."""
