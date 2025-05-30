"""Function job collections access rights table"""

import sqlalchemy as sa
from simcore_postgres_database.models._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
)

from .base import metadata
from .funcapi_function_job_collections_table import function_job_collections_table

function_job_collections_access_rights_table = sa.Table(
    "funcapi_function_job_collections_access_rights",
    metadata,
    sa.Column(
        "function_job_collection_uuid",
        sa.ForeignKey(
            function_job_collections_table.c.uuid,
            name="fk_func_access_to_func_job_colls_to_func_job_coll_uuid",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=False,
        doc="Unique identifier of the function job collection",
    ),
    sa.Column(
        "group_id",
        sa.ForeignKey(
            "groups.gid",
            name="fk_func_access_to_groups_group_id",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        nullable=True,
        doc="Group id",
    ),
    sa.Column(
        "read",
        sa.Boolean,
        default=False,
        doc="Read access right for the function job collection",
    ),
    sa.Column(
        "write",
        sa.Boolean,
        default=False,
        doc="Write access right for the function job collection",
    ),
    sa.Column(
        "execute",
        sa.Boolean,
        default=False,
        doc="Execute access right for the function job collection",
    ),
    column_created_datetime(),
    column_modified_datetime(),
    sa.PrimaryKeyConstraint(
        "function_job_collection_uuid",
        "group_id",
        name="pk_func_access_to_func_job_colls_group",
    ),
)
