""" resource_tracker_service_runs table
"""


import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._common import NUMERIC_KWARGS, column_modified_datetime
from .base import metadata

resource_tracker_licensed_items_purchases = sa.Table(
    "resource_tracker_licensed_items_purchases",
    metadata,
    sa.Column(
        "licensed_item_purchase_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column(
        "product_name",
        sa.String,
        nullable=False,
        doc="Product name",
    ),
    sa.Column(
        "licensed_item_id",
        UUID(as_uuid=True),
        nullable=False,
    ),
    sa.Column(
        "key",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "version",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        nullable=False,
    ),
    sa.Column(
        "wallet_name",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "pricing_unit_cost_id",
        sa.BigInteger,
        nullable=False,
    ),
    sa.Column(
        "pricing_unit_cost",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=True,
        doc="Pricing unit cost used for billing purposes",
    ),
    sa.Column(
        "start_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
    ),
    sa.Column(
        "expire_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
    ),
    sa.Column(
        "num_of_seats",
        sa.SmallInteger,
        nullable=False,
    ),
    sa.Column(
        "purchased_by_user",
        sa.BigInteger,
        nullable=False,
    ),
    sa.Column(
        "user_email",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "purchased_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.sql.func.now(),
    ),
    column_modified_datetime(timezone=True),
)
