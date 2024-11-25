import sqlalchemy as sa

from ._common import (
    NUMERIC_KWARGS,
    RefActions,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .payments_methods import payments_methods

#
# NOTE:
#  - This table was designed to work in an isolated database that contains only payments_* tables
#  - Specifies autorecharge settings for each wallet, including a minimum balance and primary payment methods.

payments_autorecharge = sa.Table(
    "payments_autorecharge",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        doc="Unique payment-automation identifier",
    ),
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        # NOTE: cannot use foreign-key because it would require a link to wallets table
        nullable=False,
        doc="Wallet associated to the auto-recharge",
        unique=True,
    ),
    #
    # Recharge Limits and Controls
    #
    sa.Column(
        "enabled",
        sa.Boolean,
        nullable=False,
        server_default=sa.false(),
        doc="If true, the auto-recharge is enabled on this wallet",
    ),
    sa.Column(
        "primary_payment_method_id",
        sa.String,
        sa.ForeignKey(
            payments_methods.c.payment_method_id,
            name="fk_payments_autorecharge_primary_payment_method_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        unique=True,
        doc="Primary payment method selected for auto-recharge or None if unassigned",
        # NOTE: Initially we thought 'ondelete=SET NULL' but it would require nullability and therefore dropping uniqueness
        # Not to mention the state where 'enabled=True' and 'primary_payment_method_id=None'. Finally we decided to fully
        # delete the line which will result in wallet default introduced by the api-layer. The only dissadvantage is that
        # the user would loose his previous settings.
    ),
    sa.Column(
        "top_up_amount_in_usd",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
        doc="[Required] Increase in USD when balance reaches minimum balance threshold",
    ),
    sa.Column(
        "monthly_limit_in_usd",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=True,
        server_default=None,
        doc="[Optional] Maximum amount in USD charged within a natural month"
        "If None, indicates no limit",
    ),
    # time-stamps
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)


register_modified_datetime_auto_update_trigger(payments_autorecharge)
