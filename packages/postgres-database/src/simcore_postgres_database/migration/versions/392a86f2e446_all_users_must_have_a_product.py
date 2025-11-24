"""all users must have a product

Revision ID: 392a86f2e446
Revises: 0ad000429e3d
Create Date: 2024-01-09 15:14:11.504329+00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "392a86f2e446"
down_revision = "0ad000429e3d"
branch_labels = None
depends_on = None


def upgrade():
    # If a user has NO associated product groups, assign them a default product
    migration_query = sa.text(
        """
        INSERT INTO user_to_groups (uid, gid)
        SELECT u.id, (
            SELECT p.group_id
            FROM products p
            WHERE p.group_id IS NOT NULL
            ORDER BY p.priority ASC
            LIMIT 1
        ) AS default_group_id
        FROM users u
        WHERE u.id NOT IN (
            SELECT utg.uid
            FROM user_to_groups utg
            WHERE utg.gid IN (
                SELECT p.group_id
                FROM products p
            )
        )
        AND u.status = 'ACTIVE';
    """
    )

    # Execute the migration query
    conn = op.get_bind()
    conn.execute(migration_query)


def downgrade():
    # Define the downgrade logic if needed
    pass
