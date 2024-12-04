""" resource_tracker_service_runs table
"""


import shortuuid
import sqlalchemy as sa

from ._common import column_modified_datetime
from .base import metadata


def _custom_id_generator():
    return f"rlp_{shortuuid.uuid()}"


resource_tracker_license_purchases = sa.Table(
    "resource_tracker_license_purchases",
    metadata,
    sa.Column(
        "license_purchase_id",
        sa.String,
        nullable=False,
        primary_key=True,
        default=_custom_id_generator,
    ),
    sa.Column(
        "product_name",
        sa.String,
        nullable=False,
        doc="Product name",
    ),
    sa.Column(
        "license_good_id",
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
