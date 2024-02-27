import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .users import users

#
# 'invited_users' table hold information provided by the PO of a user before the user
# row is created
#

invited_users = sa.Table(
    "invited_users",
    metadata,
    sa.Column(
        "email",
        sa.String(),
        nullable=False,
        unique=True,
        doc="Invitation issued to this email."
        "If multiple invitations to the same email (e.g. different products), then we use the same row",
    ),
    sa.Column(
        "first_name",
        sa.String(),
        doc="First name upon invitation (copied to users.first_name)",
    ),
    sa.Column(
        "last_name",
        sa.String(),
        doc="Last name upon invitation (copied to users.last_name)",
    ),
    sa.Column("company_name", sa.String()),
    # Billable address
    sa.Column("address", sa.String()),
    sa.Column("city", sa.String()),
    sa.Column("state", sa.String()),
    sa.Column("country", sa.String()),
    sa.Column("postal_code", sa.String()),
    #
    sa.Column(
        "created_by",
        sa.Integer,
        sa.ForeignKey(
            users.c.id,
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        nullable=True,
        doc="PO user that issued this invitation",
    ),
    sa.Column(
        "accepted_by",
        sa.Integer,
        sa.ForeignKey(
            users.c.id,
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=True,
        doc="Links these details to a final registered user or null if registration is pending",
    ),
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
)

register_modified_datetime_auto_update_trigger(invited_users)
