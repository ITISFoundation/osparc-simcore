import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata

users_details = sa.Table(
    "users_details",
    metadata,
    sa.Column("invite_id", sa.Integer(), primary_key=True, autoincrement=True),
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
    sa.Column(
        "email",
        sa.String(),
        nullable=False,
        unique=True,
        doc="Email associated to an invitation. Will be copied into users.email",
    ),
    sa.Column("company_name", sa.String()),
    sa.Column("address", sa.String(), doc="Billing address"),
    sa.Column("city", sa.String()),
    sa.Column("state", sa.String(), doc="State or province"),
    sa.Column("country", sa.String()),
    sa.Column("postal_code", sa.String()),
    sa.Column(
        "created_by",
        sa.Integer,
        sa.ForeignKey(
            "users.user_id",
            oupdate="CASCADE",
            ondelete="NULL",
        ),  # TODO: should be a mark instead of a reference?
        doc="PO that created this invitation",
    ),
    sa.Column(
        "accepted_by",
        sa.Integer,
        sa.ForeignKey(
            "users.user_id",
            oupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=True,
        doc="User created from this invitation",
    ),
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
)

register_modified_datetime_auto_update_trigger(users_details)
