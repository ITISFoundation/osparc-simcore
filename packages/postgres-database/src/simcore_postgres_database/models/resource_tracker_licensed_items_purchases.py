""" resource_tracker_service_runs table
"""


import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._common import column_modified_datetime
from .base import metadata

resource_tracker_licensed_items_purchases = sa.Table(
    "resource_tracker_licensed_items_purchases",
    metadata,
    sa.Column(
        "licensed_item_purchase_id",
        UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        server_default="gen_random_uuid()",
    ),
    sa.Column(
        "product_name",
        sa.String,
        nullable=False,
        doc="Product name",
    ),
    sa.Column(
        "licensed_item_id",
        sa.BigInteger,
        nullable=False,
    ),
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        nullable=False,
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
        "purchased_by_user",
        sa.BigInteger,
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
