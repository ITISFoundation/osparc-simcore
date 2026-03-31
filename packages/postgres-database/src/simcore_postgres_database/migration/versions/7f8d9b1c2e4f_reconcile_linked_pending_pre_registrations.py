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
    # Recovery policy for pending pre-registrations that are already linked to a user
    # with product access:
    #   - reviewed_by: existing > extras.invitation.issuer (if valid user_id) > NULL
    #   - reviewed_at: existing > extras.invitation.created (if valid timestamp) > users.created_at > NOW()
    #   - extras.recovery: audit metadata with source, confidence, executed_at, notes
    op.execute(
        sa.text(
            """
            UPDATE users_pre_registration_details AS upd
            SET
                account_request_status = 'APPROVED'::accountrequeststatus,

                account_request_reviewed_by = CASE
                    WHEN upd.account_request_reviewed_by IS NOT NULL
                        THEN upd.account_request_reviewed_by
                    WHEN upd.extras->'invitation'->>'issuer' ~ '^[0-9]+$'
                         AND EXISTS (
                             SELECT 1 FROM users u2
                             WHERE u2.id = (upd.extras->'invitation'->>'issuer')::bigint
                         )
                        THEN (upd.extras->'invitation'->>'issuer')::bigint
                    ELSE NULL
                END,

                account_request_reviewed_at = CASE
                    WHEN upd.account_request_reviewed_at IS NOT NULL
                        THEN upd.account_request_reviewed_at
                    WHEN upd.extras->'invitation'->>'created' ~ '^\\d{4}-\\d{2}-\\d{2}T'
                        THEN (upd.extras->'invitation'->>'created')::timestamptz
                    WHEN linked_user.created_at IS NOT NULL
                        THEN linked_user.created_at
                    ELSE NOW()
                END,

                extras = upd.extras || jsonb_build_object(
                    'recovery', jsonb_build_object(
                        'source', 'migration:7f8d9b1c2e4f',
                        'confidence', CASE
                            WHEN upd.account_request_reviewed_by IS NOT NULL
                                THEN 'high'
                            WHEN upd.extras->'invitation'->>'issuer' ~ '^[0-9]+$'
                                 AND EXISTS (
                                     SELECT 1 FROM users u3
                                     WHERE u3.id = (upd.extras->'invitation'->>'issuer')::bigint
                                 )
                                THEN 'high'
                            ELSE 'medium'
                        END,
                        'executed_at', to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                        'notes', CASE
                            WHEN upd.account_request_reviewed_by IS NOT NULL
                                THEN 'Existing reviewer preserved'
                            WHEN upd.extras->'invitation'->>'issuer' ~ '^[0-9]+$'
                                 AND EXISTS (
                                     SELECT 1 FROM users u4
                                     WHERE u4.id = (upd.extras->'invitation'->>'issuer')::bigint
                                 )
                                THEN 'Reviewer recovered from invitation issuer'
                            ELSE 'No reviewer info recoverable'
                        END
                    )
                )

            FROM users AS linked_user
            WHERE
                upd.user_id IS NOT NULL
                AND upd.user_id = linked_user.id
                AND upd.account_request_status = 'PENDING'::accountrequeststatus
                AND EXISTS (
                    SELECT 1
                    FROM user_to_groups
                    JOIN products ON products.group_id = user_to_groups.gid
                    WHERE
                        user_to_groups.uid = upd.user_id
                        AND products.name = upd.product_name
                )
            """
        )
    )


def downgrade():
    """Data migration is intentionally not reversed."""
