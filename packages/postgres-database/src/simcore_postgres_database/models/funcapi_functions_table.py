"""Functions table

- List of functions served by the simcore platform
"""

import uuid

import sqlalchemy as sa
from simcore_postgres_database.models._common import (
    column_created_datetime,
    column_modified_datetime,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import metadata

functions_table = sa.Table(
    "funcapi_functions",
    metadata,
    sa.Column(
        "uuid",
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4,
        doc="Unique id of the function",
    ),
    sa.Column(
        "title",
        sa.String,
        doc="Name of the function",
    ),
    sa.Column(
        "function_class",
        sa.String,
        doc="Class of the function",
    ),
    sa.Column(
        "description",
        sa.String,
        doc="Description of the function",
    ),
    sa.Column(
        "input_schema",
        JSONB,
        doc="Input schema of the function",
    ),
    sa.Column(
        "output_schema",
        JSONB,
        doc="Output schema of the function",
    ),
    sa.Column(
        "system_tags",
        JSONB,
        nullable=True,
        doc="System-level tags of the function",
    ),
    sa.Column(
        "user_tags",
        JSONB,
        nullable=True,
        doc="User-level tags of the function",
    ),
    sa.Column(
        "class_specific_data",
        JSONB,
        nullable=True,
        doc="Fields specific for a function class",
    ),
    sa.Column(
        "default_inputs",
        JSONB,
        nullable=True,
        doc="Default inputs of the function",
    ),
    column_created_datetime(),
    column_modified_datetime(),
    sa.PrimaryKeyConstraint("uuid", name="funcapi_functions_pk"),
)
