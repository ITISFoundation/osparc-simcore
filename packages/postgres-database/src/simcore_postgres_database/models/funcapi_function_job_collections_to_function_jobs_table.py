"""Functions table

- List of functions served by the simcore platform
"""

import sqlalchemy as sa

from ._common import RefActions, column_created_datetime, column_modified_datetime
from .base import metadata
from .funcapi_function_job_collections_table import function_job_collections_table
from .funcapi_function_jobs_table import function_jobs_table

function_job_collections_to_function_jobs_table = sa.Table(
    "funcapi_function_job_collections_to_function_jobs",
    metadata,
    sa.Column(
        "function_job_collection_uuid",
        sa.ForeignKey(
            function_job_collections_table.c.uuid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_func_job_coll_to_func_jobs_to_func_job_coll_uuid",
        ),
        nullable=False,
        doc="Unique identifier of the function job collection",
    ),
    sa.Column(
        "function_job_uuid",
        sa.ForeignKey(
            function_jobs_table.c.uuid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_func_job_coll_to_func_jobs_to_func_job_uuid",
        ),
        nullable=False,
        doc="Unique identifier of the function job",
    ),
    column_created_datetime(),
    column_modified_datetime(),
    sa.PrimaryKeyConstraint(
        "function_job_collection_uuid",
        "function_job_uuid",
        name="funcapi_function_job_collections_to_function_jobs_pk",
    ),
)
