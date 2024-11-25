import sqlalchemy as sa

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata
from .jinja2_templates import jinja2_templates

products_to_templates = sa.Table(
    "products_to_templates",
    metadata,
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_products_to_templates_product_name",
        ),
        nullable=False,
    ),
    sa.Column(
        "template_name",
        sa.String,
        sa.ForeignKey(
            jinja2_templates.c.name,
            name="fk_products_to_templates_template_name",
            ondelete=RefActions.CASCADE,
            onupdate=RefActions.CASCADE,
        ),
        nullable=True,
        doc="Custom jinja2 template",
    ),
    # TIME STAMPS ----
    column_created_datetime(timezone=False),
    column_modified_datetime(timezone=False),
    sa.UniqueConstraint("product_name", "template_name"),
)

register_modified_datetime_auto_update_trigger(products_to_templates)
