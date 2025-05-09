"""Functions table

- List of functions served by the simcore platform
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from .base import metadata

function_job_collections_table = sa.Table(
    "funcapi_function_job_collections",
    metadata,
    sa.Column(
        "uuid",
        UUID(as_uuid=True),
        default=uuid.uuid4,
        primary_key=True,
        index=True,
        doc="Unique id of the function job collection",
    ),
    sa.Column(
        "title",
        sa.String,
        doc="Title of the function job collection",
    ),
    sa.Column(
        "description",
        sa.String,
        doc="Description of the function job collection",
    ),
    sa.PrimaryKeyConstraint("uuid", name="function_job_collections_pk"),
)
