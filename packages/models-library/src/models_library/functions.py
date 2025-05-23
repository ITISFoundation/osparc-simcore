from collections.abc import Mapping
from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from common_library.errors_classes import OsparcErrorMixin
from models_library import projects
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import BaseModel, Field

from .projects import ProjectID

FunctionID: TypeAlias = UUID
FunctionJobID: TypeAlias = UUID
FileID: TypeAlias = UUID

InputTypes: TypeAlias = FileID | float | int | bool | str | list


class FunctionSchemaClass(str, Enum):
    json_schema = "application/schema+json"


class FunctionSchemaBase(BaseModel):
    schema_content: Any | None = Field(default=None)
    schema_class: FunctionSchemaClass


class JSONFunctionSchema(FunctionSchemaBase):
    schema_content: Mapping[str, Any] = Field(
        default={}, description="JSON Schema", title="JSON Schema"
    )  # json-schema library defines a schema as Mapping[str, Any]
    schema_class: FunctionSchemaClass = FunctionSchemaClass.json_schema


class JSONFunctionInputSchema(JSONFunctionSchema):
    schema_class: Literal[FunctionSchemaClass.json_schema] = (
        FunctionSchemaClass.json_schema
    )


class JSONFunctionOutputSchema(JSONFunctionSchema):
    schema_class: Literal[FunctionSchemaClass.json_schema] = (
        FunctionSchemaClass.json_schema
    )


FunctionInputSchema: TypeAlias = Annotated[
    JSONFunctionInputSchema,
    Field(discriminator="schema_class"),
]

FunctionOutputSchema: TypeAlias = Annotated[
    JSONFunctionOutputSchema,
    Field(discriminator="schema_class"),
]


class FunctionClass(str, Enum):
    PROJECT = "PROJECT"
    SOLVER = "SOLVER"
    PYTHON_CODE = "PYTHON_CODE"


FunctionClassSpecificData: TypeAlias = dict[str, Any]
FunctionJobClassSpecificData: TypeAlias = FunctionClassSpecificData


# NOTE, use InputTypes here, but api is throwing weird errors and asking for dict for elements
# see here https://github.com/ITISFoundation/osparc-simcore/issues/7659
FunctionInputs: TypeAlias = dict[str, Any] | None

FunctionInputsList: TypeAlias = list[FunctionInputs]

FunctionOutputs: TypeAlias = dict[str, Any] | None

FunctionOutputsLogfile: TypeAlias = Any


class FunctionBase(BaseModel):
    function_class: FunctionClass
    title: str = ""
    description: str = ""
    input_schema: FunctionInputSchema
    output_schema: FunctionOutputSchema
    default_inputs: FunctionInputs


class RegisteredFunctionBase(FunctionBase):
    uid: FunctionID


class ProjectFunction(FunctionBase):
    function_class: Literal[FunctionClass.PROJECT] = FunctionClass.PROJECT
    project_id: ProjectID


class RegisteredProjectFunction(ProjectFunction, RegisteredFunctionBase):
    pass


SolverJobID: TypeAlias = UUID


class SolverFunction(FunctionBase):
    function_class: Literal[FunctionClass.SOLVER] = FunctionClass.SOLVER
    solver_key: ServiceKey
    solver_version: ServiceVersion


class RegisteredSolverFunction(SolverFunction, RegisteredFunctionBase):
    pass


class PythonCodeFunction(FunctionBase):
    function_class: Literal[FunctionClass.PYTHON_CODE] = FunctionClass.PYTHON_CODE
    code_url: str


class RegisteredPythonCodeFunction(PythonCodeFunction, RegisteredFunctionBase):
    pass


Function: TypeAlias = Annotated[
    ProjectFunction | PythonCodeFunction | SolverFunction,
    Field(discriminator="function_class"),
]
RegisteredFunction: TypeAlias = Annotated[
    RegisteredProjectFunction | RegisteredPythonCodeFunction | RegisteredSolverFunction,
    Field(discriminator="function_class"),
]

FunctionJobCollectionID: TypeAlias = projects.ProjectID


class FunctionJobBase(BaseModel):
    title: str = ""
    description: str = ""
    function_uid: FunctionID
    inputs: FunctionInputs
    outputs: FunctionOutputs
    function_class: FunctionClass


class RegisteredFunctionJobBase(FunctionJobBase):
    uid: FunctionJobID


class ProjectFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.PROJECT] = FunctionClass.PROJECT
    project_job_id: ProjectID


class RegisteredProjectFunctionJob(ProjectFunctionJob, RegisteredFunctionJobBase):
    pass


class SolverFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.SOLVER] = FunctionClass.SOLVER
    solver_job_id: ProjectID


class RegisteredSolverFunctionJob(SolverFunctionJob, RegisteredFunctionJobBase):
    pass


class PythonCodeFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.PYTHON_CODE] = FunctionClass.PYTHON_CODE


class RegisteredPythonCodeFunctionJob(PythonCodeFunctionJob, RegisteredFunctionJobBase):
    pass


FunctionJob: TypeAlias = Annotated[
    ProjectFunctionJob | PythonCodeFunctionJob | SolverFunctionJob,
    Field(discriminator="function_class"),
]

RegisteredFunctionJob: TypeAlias = Annotated[
    RegisteredProjectFunctionJob
    | RegisteredPythonCodeFunctionJob
    | RegisteredSolverFunctionJob,
    Field(discriminator="function_class"),
]


class FunctionJobStatus(BaseModel):
    status: str


class FunctionJobCollection(BaseModel):
    """Model for a collection of function jobs"""

    title: str = ""
    description: str = ""
    job_ids: list[FunctionJobID] = []


class RegisteredFunctionJobCollection(FunctionJobCollection):
    uid: FunctionJobCollectionID


class FunctionJobCollectionStatus(BaseModel):
    status: list[str]


class FunctionBaseError(OsparcErrorMixin, Exception):
    pass


class FunctionIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function {function_id} not found"


class FunctionJobIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function job {function_job_id} not found"


class FunctionJobCollectionIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function job collection {function_job_collection_id} not found"


class UnsupportedFunctionClassError(FunctionBaseError):
    msg_template: str = "Function class {function_class} is not supported"


class UnsupportedFunctionJobClassError(FunctionBaseError):
    msg_template: str = "Function job class {function_job_class} is not supported"


class UnsupportedFunctionFunctionJobClassCombinationError(FunctionBaseError):
    msg_template: str = (
        "Function class {function_class} and function job class {function_job_class} combination is not supported"
    )


class FunctionInputsValidationError(FunctionBaseError):
    msg_template: str = "Function inputs validation failed: {error}"


class FunctionJobDB(BaseModel):
    function_uuid: FunctionID
    title: str = ""
    description: str = ""
    inputs: FunctionInputs
    outputs: FunctionOutputs
    class_specific_data: FunctionJobClassSpecificData
    function_class: FunctionClass


class RegisteredFunctionJobDB(FunctionJobDB):
    uuid: FunctionJobID


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


class FunctionJobCollectionDB(BaseModel):
    title: str = ""
    description: str = ""


class RegisteredFunctionJobCollectionDB(FunctionJobCollectionDB):
    uuid: FunctionJobCollectionID


class FunctionJobCollectionsListFilters(BaseModel):
    """Filters for listing function job collections"""

    has_function_id: Annotated[
        str | None,
        Field(
            description="Filter by having a function ID in the collection",
        ),
    ] = None
