"""Functions table

- List of functions served by the simcore platform
"""

import uuid

import sqlalchemy as sa
from models_library.api_schemas_webserver.functions_wb_schema import (
    FunctionJobCollectionID,
)
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from .base import metadata


class FunctionJobCollectionDB(BaseModel):
    """Model for a collection of function jobs"""

    title: str = ""
    description: str = ""


class RegisteredFunctionJobCollectionDB(FunctionJobCollectionDB):
    uuid: FunctionJobCollectionID


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
    sa.PrimaryKeyConstraint("uuid", name="funcapi_function_job_collections_pk"),
)
