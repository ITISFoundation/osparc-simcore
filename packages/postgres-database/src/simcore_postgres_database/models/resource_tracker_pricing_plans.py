""" Pricing plan table
"""
import enum

import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata


class PricingPlanClassification(str, enum.Enum):
    """
    These are our custom pricing plan classifications, each of them can have different behaviour.
    Potentional examples:
      - TIER
      - STORAGE
      - CPU_HOUR
    """

    TIER = "TIER"


resource_tracker_pricing_plans = sa.Table(
    "resource_tracker_pricing_plans",
    metadata,
    sa.Column(
        "pricing_plan_id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Identifier index",
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_rut_pricing_plans_product_name",
        ),
        nullable=False,
        doc="Products unique name",
    ),
    sa.Column(
        "display_name",
        sa.String,
        nullable=False,
        doc="Name of the pricing plan, ex. DYNAMIC_SERVICES_TIERS, CPU_HOURS, STORAGE",
    ),
    sa.Column(
        "description",
        sa.String,
        nullable=False,
        server_default="",
        doc="Description of the pricing plan",
    ),
    sa.Column(
        "classification",
        sa.Enum(PricingPlanClassification),
        nullable=False,
        doc="Pricing plan classification, ex. tier, storage, cpu_hour. Each classification can have different behaviour.",
    ),
    sa.Column(
        "is_active",
        sa.Boolean,
        nullable=False,
        doc="Is the pricing plan active",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.Column(
        "pricing_plan_key",
        sa.String,
        nullable=False,
        default=False,
        doc="Unique human readable pricing plan key that might be used for integration",
    ),
    # ---------------------------
    sa.UniqueConstraint(
        "product_name", "pricing_plan_key", name="pricing_plans_pricing_plan_key"
    ),
)
