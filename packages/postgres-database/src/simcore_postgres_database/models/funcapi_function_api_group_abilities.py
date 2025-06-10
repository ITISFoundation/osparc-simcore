"""Function related abilities of groups (read, write, execute)"""

import sqlalchemy as sa
from simcore_postgres_database.models._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)

from .base import metadata

function_api_group_abilities_table = sa.Table(
    "funcapi_function_api_group_abilities",
    metadata,
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
        "read_functions",
        sa.Boolean,
        default=False,
        doc="Ability to read functions",
    ),
    sa.Column(
        "write_functions",
        sa.Boolean,
        default=False,
        doc="Ability to write functions",
    ),
    sa.Column(
        "execute_functions",
        sa.Boolean,
        default=False,
        doc="Ability to execute functions",
    ),
    sa.Column(
        "read_function_jobs",
        sa.Boolean,
        default=False,
        doc="Ability to read function jobs",
    ),
    sa.Column(
        "write_function_jobs",
        sa.Boolean,
        default=False,
        doc="Ability to write function jobs",
    ),
    sa.Column(
        "execute_function_jobs",
        sa.Boolean,
        default=False,
        doc="Ability to execute function jobs",
    ),
    sa.Column(
        "read_function_job_collections",
        sa.Boolean,
        default=False,
        doc="Ability to read function job collections",
    ),
    sa.Column(
        "write_function_job_collections",
        sa.Boolean,
        default=False,
        doc="Ability to write function job collections",
    ),
    sa.Column(
        "execute_function_job_collections",
        sa.Boolean,
        default=False,
        doc="Ability to execute function job collections",
    ),
    column_created_datetime(),
    column_modified_datetime(),
    sa.PrimaryKeyConstraint(
        "group_id",
        "product_name",
        name="pk_func_group_product_name_to_abilities",
    ),
)
