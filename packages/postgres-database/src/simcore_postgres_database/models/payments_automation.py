import sqlalchemy as sa

from ._common import (
    NUMERIC_KWARGS,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .payments_methods import payments_methods

payments_automation = sa.Table(
    "payments_automation",
    metadata,
    sa.Column(
        "payment_method_id",
        sa.BigInteger,
        sa.ForeignKey(
            payments_methods.c.payment_method_id,
            name="fk_payments_automation_payments_method_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=False,
        doc="[Required] Payment method selected for auto-recharge",
        index=True,
        unique=True,  # only one automation per payment method
    ),
    #
    # Recharge Limits and Controls
    #
    sa.Column(
        "enabled",
        sa.Boolean,
        nullable=False,
        server_default=sa.false(),
        doc="If true, the auto-recharge is triggered",
    ),
    sa.Column(
        "min_balance_in_usd",
        sa.Numeric(**NUMERIC_KWARGS),
        nullable=False,
        server_default=sa.text("0"),
        doc="[Required] Minimum or equal balance in USD that triggers auto-recharge",
    ),
    sa.Column(
        "inc_payment_amount_in_usd",
        sa.Numeric(**NUMERIC_KWARGS),
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
)


register_modified_datetime_auto_update_trigger(payments_automation)
