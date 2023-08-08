"""add waiting for resources enum field

Revision ID: afc752d10a6c
Revises: ef931143b7cd
Create Date: 2023-07-26 13:20:10.928108+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "afc752d10a6c"
down_revision = "ef931143b7cd"
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Check if the new value already exists before attempting to add it
    enum_type_name = "statetype"
    new_value = "WAITING_FOR_RESOURCES"

    conn = op.get_bind()
    result = conn.execute(
        f"SELECT * FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '{enum_type_name}') AND enumlabel = '{new_value}'"
    )
    value_exists = result.fetchone() is not None

    if not value_exists:
        # Step 1: Use ALTER TYPE to add the new value to the existing enum
        op.execute(f"ALTER TYPE {enum_type_name} ADD VALUE '{new_value}'")


def downgrade():
    # no need to downgrade the enum type, postgres does not allow to just remove a type
    # instead the tables that use it are updated
    op.execute(
        sa.DDL(
            """
UPDATE comp_tasks SET state = 'PENDING' WHERE state = 'WAITING_FOR_RESOURCES';
UPDATE comp_pipeline SET state = 'PENDING' WHERE state = 'WAITING_FOR_RESOURCES';
UPDATE comp_runs SET result = 'PENDING' WHERE result = 'WAITING_FOR_RESOURCES';
    """
        )
    )
