import sqlalchemy as sa

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata

__all__: tuple[str, ...] = ("users_billing_details",)

users_billing_details = sa.Table(
    "users_billing_details",
    #
    # The user's billing address, i.e. the address used e.g. for invoicing.
    # This is a property of the *user* (not of a product or pre-registration):
    # one row per user, seeded once from the most recent pre-registration
    # available at account-creation time and editable by the user afterwards
    # (see users_pre_registration_details for the original, per-product
    # capture at request time).
    #
    metadata,
    sa.Column(
        "user_id",
        sa.BigInteger(),
        sa.ForeignKey(
            "users.id",
            name="fk_users_billing_details_user_id_users",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="User that owns this billing address",
    ),
    sa.Column("institution", sa.String(), doc="the name of a company or university"),
    sa.Column("address", sa.String()),
    sa.Column("city", sa.String()),
    sa.Column("state", sa.String()),
    sa.Column("country", sa.String()),
    sa.Column("postal_code", sa.String()),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    # ---------------------------
    sa.PrimaryKeyConstraint("user_id", name="users_billing_details_pkey"),
)

register_modified_datetime_auto_update_trigger(users_billing_details)
