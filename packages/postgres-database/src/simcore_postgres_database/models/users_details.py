import sqlalchemy as sa
from common_library.users_enums import AccountRequestStatus
from sqlalchemy.dialects import postgresql

from ._common import (
    RefActions,
    column_created_by_user,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .products import products  # Import the products table
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
        "id",
        sa.BigInteger,
        sa.Identity(start=1, cycle=False),
        primary_key=True,
        doc="Primary key for the pre-registration entry",
    ),
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
    # Account Request
    sa.Column(
        "account_request_status",
        sa.Enum(AccountRequestStatus),
        nullable=False,
        server_default=AccountRequestStatus.PENDING.value,
        doc="Status of review for the account request",
    ),
    sa.Column(
        "account_request_reviewed_by",
        sa.Integer,
        sa.ForeignKey(
            users.c.id,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
            name="fk_users_pre_registration_reviewed_by_user_id",
        ),
        nullable=True,
        doc="Tracks who approved or rejected the account request",
    ),
    sa.Column(
        "account_request_reviewed_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the account request was reviewed",
    ),
    # Product the user is requesting access to
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            products.c.name,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.SET_NULL,
            name="fk_users_pre_registration_details_product_name",
        ),
        nullable=True,
        doc="Product that the user is requesting an account for",
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
    column_created_by_user(users_table=users, required=False),
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
    # CONSTRAINTS:
    # Composite unique constraint to ensure a user can only have one pre-registration per product
    sa.UniqueConstraint(
        "pre_email",
        "product_name",
        name="users_pre_registration_details_pre_email_product_name_key",
    ),
)

register_modified_datetime_auto_update_trigger(users_pre_registration_details)
