""" User's confirmations table

    - Keeps a list of tokens to identify an action (registration, invitation, reset, etc) authorized
    by link to a a user in the framework
    - These tokens have an expiration date defined by configuration

"""
import enum

import sqlalchemy as sa

from ._common import RefActions
from .base import metadata
from .users import users


class ConfirmationAction(enum.Enum):
    REGISTRATION = "REGISTRATION"
    RESET_PASSWORD = "RESET_PASSWORD"  # noqa: S105
    CHANGE_EMAIL = "CHANGE_EMAIL"
    INVITATION = "INVITATION"


confirmations = sa.Table(
    "confirmations",
    metadata,
    sa.Column(
        "code",
        sa.Text,
        doc="A secret code passed by the user and associated to an action",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        doc="User id of the code issuer."
        "Removing the issuer would result in the deletion of all associated codes",
    ),
    sa.Column(
        "action",
        sa.Enum(ConfirmationAction),
        nullable=False,
        default=ConfirmationAction.REGISTRATION,
        doc="Action associated with the code",
    ),
    sa.Column(
        "data",
        sa.Text,
        doc="Extra data associated to the action. SEE handlers_confirmation.py::email_confirmation",
    ),
    sa.Column(
        "created_at",
        sa.DateTime(),
        nullable=False,
        # NOTE: that here it would be convenient to have a server_default=now()!
        doc="Creation date of this code."
        "Can be used as reference to determine the expiration date. SEE ${ACTION}_CONFIRMATION_LIFETIME",
    ),
    # constraints ----------------
    sa.PrimaryKeyConstraint("code", name="confirmation_code"),
    sa.ForeignKeyConstraint(
        ["user_id"],
        [users.c.id],
        name="user_confirmation_fkey",
        ondelete=RefActions.CASCADE,
    ),
)
