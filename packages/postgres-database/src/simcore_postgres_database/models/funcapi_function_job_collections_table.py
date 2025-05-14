import uuid

import sqlalchemy as sa
from simcore_postgres_database.models._common import (
    column_created_datetime,
    column_modified_datetime,
)
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
    column_created_datetime(),
    column_modified_datetime(),
    sa.PrimaryKeyConstraint("uuid", name="funcapi_function_job_collections_pk"),
)
