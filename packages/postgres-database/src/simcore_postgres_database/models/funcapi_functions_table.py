"""Functions table

- List of functions served by the simcore platform
"""

import uuid

import sqlalchemy as sa
from models_library.api_schemas_webserver.functions_wb_schema import (
    FunctionClass,
    FunctionClassSpecificData,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionOutputSchema,
)
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import UUID

from .base import metadata


class FunctionDB(BaseModel):
    function_class: FunctionClass
    title: str = ""
    description: str = ""
    input_schema: FunctionInputSchema
    output_schema: FunctionOutputSchema
    default_inputs: FunctionInputs
    class_specific_data: FunctionClassSpecificData


class RegisteredFunctionDB(FunctionDB):
    uuid: FunctionID


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
    sa.PrimaryKeyConstraint("uuid", name="funcapi_functions_pk"),
)
