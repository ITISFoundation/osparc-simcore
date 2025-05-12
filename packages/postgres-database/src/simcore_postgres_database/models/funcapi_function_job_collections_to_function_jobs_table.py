"""Functions table

- List of functions served by the simcore platform
"""

import sqlalchemy as sa
from sqlalchemy.sql import func

from ._common import RefActions
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
        doc="Unique identifier of the function job",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Automaticaly updates on modification of the row",
    ),
)
