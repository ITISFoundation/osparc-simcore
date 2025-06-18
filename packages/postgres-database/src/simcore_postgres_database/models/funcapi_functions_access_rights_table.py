"""Functions access rights table"""

import sqlalchemy as sa
from simcore_postgres_database.models._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)

from .base import metadata
from .funcapi_functions_table import functions_table

functions_access_rights_table = sa.Table(
    "funcapi_functions_access_rights",
    metadata,
    sa.Column(
        "function_uuid",
        sa.ForeignKey(
            functions_table.c.uuid,
            name="fk_func_access_to_func_to_func_uuid",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    sa.Column(
        "group_id",
        sa.ForeignKey(
            "groups.gid",
            name="fk_func_access_to_groups_group_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    sa.Column(
        "product_name",
        sa.ForeignKey(
            "products.name",
            name="fk_func_access_to_products_product_name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
    ),
    sa.Column(
        "read",
        sa.Boolean,
        default=False,
    ),
    sa.Column(
        "write",
        sa.Boolean,
        default=False,
    ),
    sa.Column(
        "execute",
        sa.Boolean,
        default=False,
    ),
    column_created_datetime(),
    column_modified_datetime(),
    sa.PrimaryKeyConstraint(
        "function_uuid", "group_id", "product_name", name="pk_func_access_to_func_group"
    ),
)
