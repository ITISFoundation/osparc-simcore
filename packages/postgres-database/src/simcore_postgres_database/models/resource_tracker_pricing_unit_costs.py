""" Pricing details table
    - each pricing plan table can have multiple units. These units are stored in the
    pricing details table with their unit cost. Each unit cost (row in this table) has
    id which uniquely defines the prices at this point of the time. We always store whole
    history and do not update the rows of this table.
"""
import sqlalchemy as sa

from ._common import (
    NUMERIC_KWARGS,
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)
from .base import metadata

resource_tracker_pricing_unit_costs = sa.Table(
    "resource_tracker_pricing_unit_costs",
    metadata,
    sa.Column(
        "pricing_unit_cost_id",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Identifier index",
    ),
    sa.Column(
        "pricing_plan_id",
        sa.BigInteger,
        sa.ForeignKey(
            "resource_tracker_pricing_plans.pricing_plan_id",
            name="fk_resource_tracker_pricing_units_costs_pricing_plan_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Foreign key to pricing plan",
        index=True,
    ),
    sa.Column(
        "pricing_plan_key",
        sa.String,
        nullable=False,
        doc="Parent pricing key (storing for historical reasons)",
    ),
    sa.Column(
        "pricing_unit_id",
        sa.BigInteger,
        sa.ForeignKey(
            "resource_tracker_pricing_units.pricing_unit_id",
            name="fk_resource_tracker_pricing_units_costs_pricing_unit_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Foreign key to pricing unit",
        index=True,
    ),
    sa.Column(
        "pricing_unit_name",
        sa.String,
        nullable=False,
        doc="Parent pricing unit name (storing for historical reasons)",
    ),
    sa.Column(
        "cost_per_unit",
        sa.Numeric(**NUMERIC_KWARGS),  # type: ignore
        nullable=False,
        doc="The cost per unit of the pricing plan in credits.",
    ),
    sa.Column(
        "valid_from",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="From when the pricing unit is active",
    ),
    sa.Column(
        "valid_to",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="To when the pricing unit was active, if null it is still active",
        index=True,
    ),
    column_created_datetime(timezone=True),
    sa.Column(
        "comment",
        sa.String,
        nullable=True,
        doc="Option to store comment",
    ),
    column_modified_datetime(timezone=True),
)
