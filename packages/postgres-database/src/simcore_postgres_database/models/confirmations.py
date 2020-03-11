""" User's confirmations table

    - Keeps a list of tokens to identify an action (registration, invitation, reset, etc) authorized
    by link to a a user in the framework
    - These tokens have an expiration date defined by configuration

"""
import enum
import sqlalchemy as sa

from .base import metadata
from .users import users


class ConfirmationAction(enum.Enum):
    REGISTRATION = "REGISTRATION"
    RESET_PASSWORD = "RESET_PASSWORD"
    CHANGE_EMAIL = "CHANGE_EMAIL"
    INVITATION = "INVITATION"


confirmations = sa.Table(
    "confirmations",
    metadata,
    sa.Column("code", sa.Text),
    sa.Column("user_id", sa.BigInteger),
    sa.Column(
        "action",
        sa.Enum(ConfirmationAction),
        nullable=False,
        default=ConfirmationAction.REGISTRATION,
    ),
    sa.Column("data", sa.Text),  # TODO: json?
    sa.Column("created_at", sa.DateTime, nullable=False),
    #
    sa.PrimaryKeyConstraint("code", name="confirmation_code"),
    sa.ForeignKeyConstraint(
        ["user_id"], [users.c.id], name="user_confirmation_fkey", ondelete="CASCADE"
    ),
)
