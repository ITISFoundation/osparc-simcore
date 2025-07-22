import datetime
from typing import Annotated, TypeAlias

from pydantic import Field

from ..functions import (
    Function,
    FunctionAccessRights,
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


class RegisteredSolverFunctionGet(RegisteredSolverFunction, OutputSchema): ...


class RegisteredProjectFunctionGet(RegisteredProjectFunction, OutputSchema):
    uid: Annotated[FunctionID, Field(alias="uuid")]
    project_id: Annotated[ProjectID, Field(alias="templateId")]
    created_at: Annotated[datetime.datetime, Field(alias="creationDate")]
    modified_at: Annotated[datetime.datetime, Field(alias="lastChangeDate")]
    access_rights: FunctionAccessRights | None = None
    thumbnail: str | None = None


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
