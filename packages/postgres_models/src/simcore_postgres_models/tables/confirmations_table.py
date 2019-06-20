import sqlalchemy as sa

from .base import metadata

confirmations = sa.Table("confirmations", metadata,
    sa.Column("code", sa.Text),
    sa.Column("user_id", sa.BigInteger),
    sa.Column("action",
        sa.Enum(ConfirmationAction),
        nullable=False,
        default=ConfirmationAction.REGISTRATION
    ),
    sa.Column("data", sa.Text), # TODO: json?
    sa.Column("created_at", sa.DateTime, nullable=False),

    #
    sa.PrimaryKeyConstraint("code", name="confirmation_code"),
    sa.ForeignKeyConstraint(["user_id"], [users.c.id],
                            name="user_confirmation_fkey",
                            ondelete="CASCADE"),
 )
