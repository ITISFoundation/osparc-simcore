""" resource_tracker_service_runs table
"""

import enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata


class LicensedResourceType(str, enum.Enum):
    VIP_MODEL = "VIP_MODEL"


licensed_items = sa.Table(
    "licensed_items",
    metadata,
    sa.Column(
        "licensed_item_id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
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
        "display_name",
        sa.String,
        nullable=False,
        doc="Display name for front-end",
    ),
    sa.Column(
        "licensed_resource_type",
        sa.Enum(LicensedResourceType),
        nullable=False,
        doc="Resource type, ex. VIP_MODEL",
    ),
    sa.Column(
        "pricing_plan_id",
        sa.BigInteger,
        sa.ForeignKey(
            "resource_tracker_pricing_plans.pricing_plan_id",
            name="fk_resource_tracker_license_packages_pricing_plan_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.RESTRICT,
        ),
        nullable=False,
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_resource_tracker_license_packages_product_name",
        ),
        nullable=False,
        doc="Product name identifier. If None, then the item is not exposed",
    ),
    sa.Column(
        "is_hidden_on_market",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
        doc="If true, the item is not listed on the market. (Public API might want to see all of them, even if they are not listed on the Market)",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Index("idx_licensed_items_key_version", "key", "version", unique=True),
)
