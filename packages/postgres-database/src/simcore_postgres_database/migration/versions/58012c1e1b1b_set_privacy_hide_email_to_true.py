"""set privacy_hide_email to true. Reverts "set privacy_hide_email to false temporarily" (5e27063c3ac9)

Revision ID: 58012c1e1b1b
Revises: 77ac824a77ff
Create Date: 2024-12-17 10:13:24.800681+00:00

"""
from alembic import op
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "58012c1e1b1b"
down_revision = "77ac824a77ff"
branch_labels = None
depends_on = None


def upgrade():
    # server_default of privacy_hide_email to true
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("privacy_hide_email", server_default=expression.true())

    # Reset all to default: Revert existing values in the database to true
    op.execute("UPDATE users SET privacy_hide_email = true")


def downgrade():
    # Change the server_default of privacy_hide_email to false
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("privacy_hide_email", server_default=expression.false())

    # Reset all to default: Update existing values in the database
    op.execute("UPDATE users SET privacy_hide_email = false")
