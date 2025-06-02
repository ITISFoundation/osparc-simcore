"""Function jobs access rights table"""

import sqlalchemy as sa
from simcore_postgres_database.models._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)

from .base import metadata
from .funcapi_function_jobs_table import function_jobs_table

function_jobs_access_rights_table = sa.Table(
    "funcapi_function_jobs_access_rights",
    metadata,
    sa.Column(
        "function_job_uuid",
        sa.ForeignKey(
            function_jobs_table.c.uuid,
            name="fk_func_access_to_func_jobs_to_func_job_uuid",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Unique identifier of the function job",
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
        doc="Group id",
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
        doc="Name of the product",
    ),
    sa.Column(
        "read",
        sa.Boolean,
        default=False,
        doc="Read access right for the function job",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        default=False,
        doc="Write access right for the function job",
    ),
    sa.Column(
        "execute",
        sa.Boolean,
        default=False,
        doc="Execute access right for the function job",
    ),
    column_created_datetime(),
    column_modified_datetime(),
    sa.PrimaryKeyConstraint(
        "function_job_uuid",
        "group_id",
        "product_name",
        name="pk_func_access_to_func_jobs_group",
    ),
)
