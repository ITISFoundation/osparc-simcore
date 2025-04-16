"""Functions table

- List of functions served by the simcore platform
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._common import RefActions
from .base import metadata

functions = sa.Table(
    "functions",
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
        sa.JSON,
        doc="Input schema of the function",
    ),
    sa.Column(
        "output_schema",
        sa.JSON,
        doc="Output schema of the function",
    ),
    sa.Column(
        "system_tags",
        sa.JSON,
        nullable=True,
        doc="System-level tags of the function",
    ),
    sa.Column(
        "user_tags",
        sa.JSON,
        nullable=True,
        doc="User-level tags of the function",
    ),
    sa.Column(
        "class_specific_data",
        sa.JSON,
        nullable=True,
        doc="Fields specific for a function class",
    ),
    sa.Column(
        "default_inputs",
        sa.JSON,
        nullable=True,
        doc="Default inputs of the function",
    ),
    sa.PrimaryKeyConstraint("uuid", name="functions_pk"),
)

function_jobs = sa.Table(
    "function_jobs",
    metadata,
    sa.Column(
        "uuid",
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4,
        doc="Unique id of the function job",
    ),
    sa.Column(
        "title",
        sa.String,
        doc="Name of the function job",
    ),
    sa.Column(
        "function_uuid",
        sa.ForeignKey(
            functions.c.uuid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_functions_to_function_jobs_to_function_uuid",
        ),
        nullable=False,
        index=True,
        doc="Unique identifier of the function",
    ),
    sa.Column(
        "function_class",
        sa.String,
        doc="Class of the function",
    ),
    sa.Column(
        "status",
        sa.String,
        doc="Status of the function job",
    ),
    sa.Column(
        "inputs",
        sa.JSON,
        doc="Inputs of the function job",
    ),
    sa.Column(
        "outputs",
        sa.JSON,
        doc="Outputs of the function job",
    ),
    sa.Column(
        "class_specific_data",
        sa.JSON,
        nullable=True,
        doc="Fields specific for a function class",
    ),
    sa.PrimaryKeyConstraint("uuid", name="function_jobs_pk"),
)

function_job_collections = sa.Table(
    "function_job_collections",
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
        "name",
        sa.String,
        doc="Name of the function job collection",
    ),
    sa.PrimaryKeyConstraint("uuid", name="function_job_collections_pk"),
)

function_job_collections_to_function_jobs = sa.Table(
    "function_job_collections_to_function_jobs",
    metadata,
    sa.Column(
        "function_job_collection_uuid",
        sa.ForeignKey(
            function_job_collections.c.uuid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_func_job_coll_to_func_jobs_to_func_job_coll_uuid",
        ),
        doc="Unique identifier of the function job collection",
    ),
    sa.Column(
        "function_job_uuid",
        sa.ForeignKey(
            function_jobs.c.uuid,
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_func_job_coll_to_func_jobs_to_func_job_uuid",
        ),
        doc="Unique identifier of the function job",
    ),
)
