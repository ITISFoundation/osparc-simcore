""" resource_tracker_service_runs table
"""

import enum

import shortuuid
import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata


def _custom_id_generator():
    return f"lgo_{shortuuid.uuid()}"


class LicensedResourceType(str, enum.Enum):
    VIP_MODEL = "VIP_MODEL"


licensed_items = sa.Table(
    "licensed_items",
    metadata,
    sa.Column(
        "licensed_item_id",
        sa.String,
        nullable=False,
        primary_key=True,
        default=_custom_id_generator,
    ),
    sa.Column(
        "name",
        sa.String,
        nullable=False,
    ),
    sa.Column(
        "licensed_resource_type",
        sa.Enum(LicensedResourceType),
        nullable=False,
        doc="Item type, ex. VIP_MODEL",
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
        doc="Product name",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)
