import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .users import users

#
# invited_user table hold information provided by the PO of a user before the user
# row is created
#

invited_user = sa.Table(
    "invited_user",
    metadata,
    sa.Column(
        "email",
        sa.String(),
        nullable=False,
        unique=True,
        doc="Email associated to an invitation. Will be copied into users.email",
    ),
    sa.Column(
        "first_name",
        sa.String(),
        doc="First name as provided during invitation. Will be copied into users.first_name",
    ),
    sa.Column(
        "last_name",
        sa.String(),
        doc="Last name as provided during invitation. Will be copied into users.last_name",
    ),
    sa.Column("company_name", sa.String()),
    sa.Column("address", sa.String(), doc="Billing address"),
    sa.Column("city", sa.String()),
    sa.Column("state", sa.String(), doc="State or province"),
    sa.Column("country", sa.String(), doc="Country symbol"),
    sa.Column("postal_code", sa.String()),
    sa.Column(
        "created_by",
        sa.Integer,
        sa.ForeignKey(
            users.c.id,
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        nullable=True,
        doc="PO that created an invitation",
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
        doc="Links this user details with user",
    ),
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
)

register_modified_datetime_auto_update_trigger(invited_user)
