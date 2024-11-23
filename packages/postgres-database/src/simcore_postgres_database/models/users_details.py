import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .users import users

users_pre_registration_details = sa.Table(
    "users_pre_registration_details",
    #
    # Provides extra attributes for a user that either not required or that are provided before the user is created.
    # The latter state is denoted as "pre-registration" and specific attributes in this state are prefixed with `pre_`. Therefore,
    # a row can be added in this table during pre-registration i.e. even before the `users` row exists.
    #
    metadata,
    sa.Column(
        "user_id",
        sa.Integer,
        sa.ForeignKey(
            users.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=True,
        doc="None if row was added during pre-registration or join column with `users` after registration",
    ),
    # Pre-registration columns: i.e. fields copied to `users` upon registration
    sa.Column(
        "pre_email",
        sa.String(),
        nullable=False,
        unique=True,
        doc="Email of the user on pre-registration (copied to users.email upon registration)",
    ),
    sa.Column(
        "pre_first_name",
        sa.String(),
        doc="First name on pre-registration (copied to users.first_name upon registration)",
    ),
    sa.Column(
        "pre_last_name",
        sa.String(),
        doc="Last name on pre-registration (copied to users.last_name upon registration)",
    ),
    sa.Column(
        "pre_phone",
        sa.String(),
        doc="Phone provided on pre-registration"
        "NOTE: this is not copied upon registration since it needs to be confirmed",
    ),
    # Billable address columns:
    sa.Column("institution", sa.String(), doc="the name of a company or university"),
    sa.Column("address", sa.String()),
    sa.Column("city", sa.String()),
    sa.Column("state", sa.String()),
    sa.Column("country", sa.String()),
    sa.Column("postal_code", sa.String()),
    sa.Column(
        "extras",
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        doc="Extra information provided in the form but still not defined as a column.",
    ),
    # Other related users
    sa.Column(
        "created_by",
        sa.Integer,
        sa.ForeignKey(
            users.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
        ),
        nullable=True,
        doc="PO user that issued this pre-registration",
    ),
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
)

register_modified_datetime_auto_update_trigger(users_pre_registration_details)
