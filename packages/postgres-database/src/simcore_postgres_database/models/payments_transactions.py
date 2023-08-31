import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata

payments_transactions = sa.Table(
    "payments_transactions",
    metadata,
    sa.Column(
        "payment_id",
        sa.String,
        nullable=False,
        primary_key=True,
        doc="Identifer of the payment provided by payment gateway",
    ),
    sa.Column(
        "amount",
        sa.Numeric(scale=2),
        nullable=False,
        doc="Total amount of the transaction (in dollars). E.g. 1234.12 $",
    ),
    #
    # Concept/Info
    #
    sa.Column(
        "credits",
        sa.Numeric(scale=2),
        nullable=False,
        doc="Amount of credits that will be added to the wallet_id "
        "once the transaction completes successfuly."
        "E.g. 1234.12 credits",
    ),
    sa.Column(
        "product_name",
        sa.String,
        nullable=False,
        doc="Product name from which the transaction took place",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        nullable=False,
        doc="User unique identifier",
        index=True,
    ),
    sa.Column(
        "user_email",
        sa.String,
        nullable=False,
        doc="User email  at the time of the transaction",
    ),
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        nullable=False,
        doc="Wallet identifier owned by the user",
        index=True,
    ),
    sa.Column(
        "wallet_name",
        sa.String,
        nullable=False,
        doc="Wallet name at the time of the transaction",
    ),
    sa.Column(
        "comment",
        sa.Text,
        nullable=True,
        doc="Extra comment on this payment (optional)",
    ),
    #
    # States
    #
    sa.Column(
        "initiated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamps when transaction initated (successful respose to /init)",
    ),
    sa.Column(
        "completed_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Timestamps when transaction completed (payment acked)",
    ),
    sa.Column(
        "success",
        sa.Boolean,
        nullable=True,
        doc="Transation still incomplete (=null) or "
        "completed successfuly (=true) "
        "completed with failures (=false).",
    ),
    sa.Column(
        "errors",
        sa.Text,
        nullable=True,
        doc="Stores error messages in case of transaction failure",
    ),
    # timestamps for this row
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)


register_modified_datetime_auto_update_trigger(payments_transactions)
