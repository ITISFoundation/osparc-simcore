import datetime
from typing import Annotated, TypeAlias

from pydantic import ConfigDict, Field, HttpUrl

from ..functions import (
    Function,
    FunctionBase,
    FunctionClass,
    FunctionClassSpecificData,
    FunctionID,
    FunctionIDString,
    FunctionInputs,
    FunctionInputSchema,
    FunctionInputsList,
    FunctionJob,
    FunctionJobClassSpecificData,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionsListFilters,
    FunctionJobCollectionStatus,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionOutputSchema,
    FunctionSchemaClass,
    FunctionUpdate,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    ProjectFunction,
    ProjectFunctionJob,
    RegisteredFunction,
    RegisteredFunctionBase,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredSolverFunction,
    SolverFunction,
    SolverFunctionJob,
)
from ..functions_errors import (
    FunctionIDNotFoundError,
    FunctionInputsValidationError,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobIDNotFoundError,
    FunctionReadAccessDeniedError,
    UnsupportedFunctionClassError,
    UnsupportedFunctionFunctionJobClassCombinationError,
)
from ..groups import GroupID
from ..projects import ProjectID
from ._base import InputSchema, OutputSchema

__all__ = [
    "Function",
    "FunctionBase",
    "FunctionClass",
    "FunctionClassSpecificData",
    "FunctionClassSpecificData",
    "FunctionID",
    "FunctionID",
    "FunctionIDNotFoundError",
    "FunctionIDNotFoundError",
    "FunctionIDString",
    "FunctionInputSchema",
    "FunctionInputs",
    "FunctionInputs",
    "FunctionInputsList",
    "FunctionInputsList",
    "FunctionInputsValidationError",
    "FunctionInputsValidationError",
    "FunctionJob",
    "FunctionJobClassSpecificData",
    "FunctionJobClassSpecificData",
    "FunctionJobCollection",
    "FunctionJobCollectionID",
    "FunctionJobCollectionID",
    "FunctionJobCollectionIDNotFoundError",
    "FunctionJobCollectionIDNotFoundError",
    "FunctionJobCollectionStatus",
    "FunctionJobCollectionStatus",
    "FunctionJobCollectionsListFilters",
    "FunctionJobID",
    "FunctionJobID",
    "FunctionJobIDNotFoundError",
    "FunctionJobIDNotFoundError",
    "FunctionJobStatus",
    "FunctionJobStatus",
    "FunctionOutputSchema",
    "FunctionOutputs",
    "FunctionReadAccessDeniedError",
    "FunctionSchemaClass",
    "FunctionToRegister",
    "FunctionToRegister",
    "JSONFunctionInputSchema",
    "JSONFunctionOutputSchema",
    "ProjectFunction",
    "ProjectFunctionJob",
    "RegisteredFunction",
    "RegisteredFunctionBase",
    "RegisteredFunctionGet",
    "RegisteredFunctionJob",
    "RegisteredFunctionJobCollection",
    "RegisteredProjectFunction",
    "RegisteredProjectFunctionGet",
    "RegisteredProjectFunctionJob",
    "RegisteredSolverFunction",
    "RegisteredSolverFunctionGet",
    "SolverFunction",
    "SolverFunctionJob",
    "UnsupportedFunctionClassError",
    "UnsupportedFunctionFunctionJobClassCombinationError",
]


class FunctionGroupAccessRightsGet(OutputSchema):
    read: bool
    write: bool
    execute: bool


class FunctionGroupAccessRightsUpdate(InputSchema):
    read: bool
    write: bool
    execute: bool


class RegisteredSolverFunctionGet(RegisteredSolverFunction, OutputSchema):
    uid: Annotated[FunctionID, Field(alias="uuid")]
    created_at: Annotated[datetime.datetime, Field(alias="creationDate")]
    modified_at: Annotated[datetime.datetime, Field(alias="lastChangeDate")]
    access_rights: dict[GroupID, FunctionGroupAccessRightsGet]
    thumbnail: HttpUrl | None = None


class RegisteredProjectFunctionGet(RegisteredProjectFunction, OutputSchema):
    uid: Annotated[FunctionID, Field(alias="uuid")]
    project_id: Annotated[ProjectID, Field(alias="templateId")]
    created_at: Annotated[datetime.datetime, Field(alias="creationDate")]
    modified_at: Annotated[datetime.datetime, Field(alias="lastChangeDate")]
    access_rights: dict[GroupID, FunctionGroupAccessRightsGet]
    thumbnail: HttpUrl | None = None
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "function_class": "PROJECT",
                    "title": "Example Project Function",
                    "description": "This is an example project function.",
                    "input_schema": {
                        "schema_content": {
                            "type": "object",
                            "properties": {"input1": {"type": "integer"}},
                        },
                        "schema_class": "application/schema+json",
                    },
                    "output_schema": {
                        "schema_content": {
                            "type": "object",
                            "properties": {"output1": {"type": "string"}},
                        },
                        "schema_class": "application/schema+json",
                    },
                    "default_inputs": None,
                    "project_id": "11111111-1111-1111-1111-111111111111",
                    "uid": "22222222-2222-2222-2222-222222222222",
                    "created_at": "2024-01-01T12:00:00",
                    "modified_at": "2024-01-02T12:00:00",
                    "access_rights": {
                        "5": {
                            "read": True,
                            "write": False,
                            "execute": True,
                        }
                    },
                    "thumbnail": None,
                },
            ]
        },
    )


class SolverFunctionToRegister(SolverFunction, InputSchema): ...


class ProjectFunctionToRegister(ProjectFunction, InputSchema): ...


FunctionToRegister: TypeAlias = Annotated[
    ProjectFunctionToRegister | SolverFunctionToRegister,
    Field(discriminator="function_class"),
]

RegisteredFunctionGet: TypeAlias = Annotated[
    RegisteredProjectFunctionGet | RegisteredSolverFunctionGet,
    Field(discriminator="function_class"),
]


class RegisteredFunctionUpdate(FunctionUpdate, InputSchema): ...
