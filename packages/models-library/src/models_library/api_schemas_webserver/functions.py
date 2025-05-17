# pylint: disable=unused-import

from typing import Annotated, TypeAlias

from pydantic import Field

from ..functions import (  # noqa: F401
    Function,
    FunctionBase,
    FunctionClass,
    FunctionClassSpecificData,
    FunctionID,
    FunctionIDNotFoundError,
    FunctionInputs,
    FunctionInputSchema,
    FunctionInputsList,
    FunctionInputsValidationError,
    FunctionJob,
    FunctionJobClassSpecificData,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobCollectionStatus,
    FunctionJobID,
    FunctionJobIDNotFoundError,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionOutputSchema,
    FunctionSchemaClass,
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
    UnsupportedFunctionClassError,
    UnsupportedFunctionFunctionJobClassCombinationError,
)
from ._base import InputSchema, OutputSchema


class RegisteredSolverFunctionGet(RegisteredSolverFunction, OutputSchema): ...


class RegisteredProjectFunctionGet(RegisteredProjectFunction, OutputSchema): ...


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
