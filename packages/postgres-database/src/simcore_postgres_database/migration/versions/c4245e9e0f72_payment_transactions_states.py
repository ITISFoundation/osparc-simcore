"""payment transactions states

Revision ID: c4245e9e0f72
Revises: fc6ea424f586
Create Date: 2023-09-07 16:00:26.832441+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c4245e9e0f72"
down_revision = "fc6ea424f586"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    payment_transaction_state = postgresql.ENUM(
        "PENDING",
        "SUCCESS",
        "FAILED",
        "CANCELED",
        name="paymenttransactionstate",
    )
    payment_transaction_state.create(connection)

    op.add_column(
        "payments_transactions",
        sa.Column(
            "state",
            sa.Enum(
                "PENDING",
                "SUCCESS",
                "FAILED",
                "CANCELED",
                name="paymenttransactionstate",
            ),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column(
        "payments_transactions", sa.Column("state_message", sa.Text(), nullable=True)
    )
    connection.execute(
        sa.DDL(
            "UPDATE payments_transactions SET state = 'SUCCESS' WHERE success = true"
        )
    )
    connection.execute(
        sa.DDL(
            "UPDATE payments_transactions SET state = 'FAILED' WHERE success = false"
        )
    )
    connection.execute(
        sa.DDL(
            "UPDATE payments_transactions SET state = 'PENDING' WHERE success IS NULL"
        )
    )
    connection.execute("UPDATE payments_transactions SET state_message = errors")

    op.drop_column("payments_transactions", "success")
    op.drop_column("payments_transactions", "errors")


def downgrade():
    op.add_column(
        "payments_transactions",
        sa.Column("errors", sa.TEXT(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "payments_transactions",
        sa.Column("success", sa.BOOLEAN(), autoincrement=False, nullable=True),
    )

    connection = op.get_bind()
    connection.execute(
        sa.DDL(
            "UPDATE payments_transactions SET success = true WHERE state = 'SUCCESS'"
        )
    )
    connection.execute(
        sa.DDL(
            "UPDATE payments_transactions SET success = false WHERE completed_at IS NOT NULL AND state != 'SUCCESS'"
        )
    )
    connection.execute(
        sa.DDL(
            "UPDATE payments_transactions SET success = NULL WHERE completed_at IS NULL AND state != 'SUCCESS'"
        )
    )

    op.drop_column("payments_transactions", "state_message")
    op.drop_column("payments_transactions", "state")

    sa.Enum(name="paymenttransactionstate").drop(connection, checkfirst=False)
