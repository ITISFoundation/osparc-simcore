"""set privacy_hide_email to false temporarily

Revision ID: 5e27063c3ac9
Revises: 4d007819e61a
Create Date: 2024-12-10 15:50:48.024204+00:00

"""
from alembic import op
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "5e27063c3ac9"
down_revision = "4d007819e61a"
branch_labels = None
depends_on = None


def upgrade():
    # Change the server_default of privacy_hide_email to false
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("privacy_hide_email", server_default=expression.false())

    # Reset all to default: Update existing values in the database
    op.execute("UPDATE users SET privacy_hide_email = false")


def downgrade():

    # Revert the server_default of privacy_hide_email to true
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("privacy_hide_email", server_default=expression.true())

    # Reset all to default: Revert existing values in the database to true
    op.execute("UPDATE users SET privacy_hide_email = true")
