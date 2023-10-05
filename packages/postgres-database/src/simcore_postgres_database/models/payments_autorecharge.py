import sqlalchemy as sa

from ._common import (
    NUMERIC_KWARGS,
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
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=False,
        doc="[Required] Primary payment method selected for auto-recharge",
        unique=True,
    ),
    sa.Column(
        "min_balance_in_usd",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
        server_default=sa.text("0"),
        doc="[Required] Minimum or equal balance in USD that triggers auto-recharge",
    ),
    sa.Column(
        "inc_payment_amount_in_usd",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
        doc="[Required] Increase in USD when balance reaches min_balance_in_usd",
    ),
    sa.Column(
        "inc_payments_countdown",
        sa.Integer(),
        nullable=True,
        server_default=None,
        doc="[Optional] Number of auto-recharges left."
        "If it reaches zero, then auto-recharge stops."
        "Used to limit the number of times that the system can auto-recharge."
        "If None, then inc has no limit.",
    ),
    # time-stamps
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    #
    sa.CheckConstraint(
        "(inc_payments_countdown >= 0) OR (inc_payments_countdown IS NULL)",
        name="check_inc_payments_countdown_nonnegative",
    ),
)


register_modified_datetime_auto_update_trigger(payments_autorecharge)
