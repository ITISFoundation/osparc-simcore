""" Tables connected to credits
    - resource_tracker_credit_mapping table
    - resource_tracker_credit_history table
"""
import enum

import sqlalchemy as sa

from ._common import column_modified_datetime
from .base import metadata


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TransactionClassification(str, enum.Enum):
    TOP_UP = "TOP_UP"  # user top up credits
    DEDUCTION_SERVICE_RUN = (
        "DEDUCTION_SERVICE_RUN"  # computational/dynamic service run costs
    )


resource_tracker_wallets_credit_transactions = sa.Table(
    "resource_tracker_wallets_credit_transactions",
    metadata,
    sa.Column(
        "transaction_id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Identifier index",
    ),
    sa.Column(
        "product_name",
        sa.String,
        nullable=False,
        doc="Product name",
        index=True,
    ),
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        nullable=False,
        doc="Wallet id",
        index=True,
    ),
    sa.Column(
        "wallet_name",
        sa.String,
        nullable=False,
        doc="Wallet name",
        index=True,
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        nullable=False,
        doc="User id",
    ),
    sa.Column(
        "user_email",
        sa.String,
        nullable=False,
        doc="User email",
    ),
    sa.Column(
        "credits",
        sa.Numeric(precision=3, scale=2),
        nullable=False,
        doc="Credits",
    ),
    sa.Column(
        "transaction_status",
        sa.Enum(TransactionStatus),
        nullable=True,
        doc="Transaction status, ex. PENDING, COMPLETED, FAILED",
        index=True,
    ),
    sa.Column(
        "transaction_classification",
        sa.Enum(TransactionClassification),
        nullable=True,
        doc="Transaction classification, ex. TOP_UP, DEDUCTION_SERVICE_RUN, DEDUCTION_STORAGE",
        index=True,
    ),
    sa.Column(
        "service_run_id",
        sa.BigInteger,
        nullable=True,
        doc="Service run id connected with this transaction",
        index=True,
    ),
    column_modified_datetime(timezone=True),
    # ---------------------------
)
