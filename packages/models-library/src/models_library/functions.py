import datetime
from collections.abc import Mapping
from enum import Enum
from typing import Annotated, Any, Final, Literal, TypeAlias
from uuid import UUID

from models_library import projects
from models_library.basic_regex import UUID_RE_BASE
from models_library.basic_types import ConstrainedStr
from models_library.batch_operations import BatchCreateEnvelope
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, ConfigDict, Field

from .batch_operations import BatchGetEnvelope, BatchUpdateEnvelope
from .projects import ProjectID
from .utils.change_case import snake_to_camel

TaskID: TypeAlias = str
FunctionID: TypeAlias = UUID
FunctionJobID: TypeAlias = UUID
FileID: TypeAlias = UUID

InputTypes: TypeAlias = FileID | float | int | bool | str | list
_MAX_LIST_LENGTH: Final[int] = 50


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

FunctionInputsList: TypeAlias = Annotated[
    list[FunctionInputs],
    Field(max_length=_MAX_LIST_LENGTH),
]


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
    created_at: datetime.datetime
    modified_at: datetime.datetime


class FunctionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class ProjectFunction(FunctionBase):
    function_class: Literal[FunctionClass.PROJECT] = FunctionClass.PROJECT
    project_id: ProjectID


class RegisteredProjectFunction(ProjectFunction, RegisteredFunctionBase):
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
                },
            ]
        },
    )


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


class ProjectFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.PROJECT] = FunctionClass.PROJECT
    project_job_id: ProjectID | None
    job_creation_task_id: TaskID | None


class RegisteredProjectFunctionJobPatch(BaseModel):
    function_class: Literal[FunctionClass.PROJECT] = FunctionClass.PROJECT
    title: str | None
    description: str | None
    inputs: FunctionInputs
    outputs: FunctionOutputs
    project_job_id: ProjectID | None
    job_creation_task_id: TaskID | None


class SolverFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.SOLVER] = FunctionClass.SOLVER
    solver_job_id: ProjectID | None
    job_creation_task_id: TaskID | None


class RegisteredSolverFunctionJobPatch(BaseModel):
    function_class: Literal[FunctionClass.SOLVER] = FunctionClass.SOLVER
    title: str | None
    description: str | None
    inputs: FunctionInputs
    outputs: FunctionOutputs
    solver_job_id: ProjectID | None
    job_creation_task_id: TaskID | None


class PythonCodeFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.PYTHON_CODE] = FunctionClass.PYTHON_CODE


class RegisteredPythonCodeFunctionJobPatch(BaseModel):
    function_class: Literal[FunctionClass.PYTHON_CODE] = FunctionClass.PYTHON_CODE
    title: str | None
    inputs: FunctionInputs
    outputs: FunctionOutputs
    description: str | None


FunctionJob: TypeAlias = Annotated[
    ProjectFunctionJob | PythonCodeFunctionJob | SolverFunctionJob,
    Field(discriminator="function_class"),
]
FunctionJobList: TypeAlias = Annotated[
    list[FunctionJob], Field(max_length=_MAX_LIST_LENGTH)
]


class RegisteredFunctionJobBase(FunctionJobBase):
    uid: FunctionJobID
    created_at: datetime.datetime


class RegisteredProjectFunctionJob(ProjectFunctionJob, RegisteredFunctionJobBase):
    pass


class RegisteredSolverFunctionJob(SolverFunctionJob, RegisteredFunctionJobBase):
    pass


class RegisteredPythonCodeFunctionJob(PythonCodeFunctionJob, RegisteredFunctionJobBase):
    pass


RegisteredFunctionJob: TypeAlias = Annotated[
    RegisteredProjectFunctionJob
    | RegisteredPythonCodeFunctionJob
    | RegisteredSolverFunctionJob,
    Field(discriminator="function_class"),
]


class BatchCreateRegisteredFunctionJobs(BatchCreateEnvelope[RegisteredFunctionJob]):
    pass


class BatchUpdateRegisteredFunctionJobs(BatchUpdateEnvelope[RegisteredFunctionJob]):
    pass


class BatchGetCachedRegisteredFunctionJobs(
    BatchGetEnvelope[RegisteredFunctionJob, FunctionInputs]
):
    pass


RegisteredFunctionJobPatch = Annotated[
    RegisteredProjectFunctionJobPatch
    | RegisteredPythonCodeFunctionJobPatch
    | RegisteredSolverFunctionJobPatch,
    Field(discriminator="function_class"),
]


class FunctionJobPatchRequest(BaseModel):
    uid: FunctionJobID
    patch: RegisteredFunctionJobPatch


FunctionJobPatchRequestList: TypeAlias = Annotated[
    list[FunctionJobPatchRequest],
    Field(
        max_length=_MAX_LIST_LENGTH,
        description="List of function job patch requests",
    ),
]


class FunctionJobStatus(BaseModel):
    status: str


class RegisteredFunctionJobWithStatusBase(RegisteredFunctionJobBase, FunctionJobBase):
    status: FunctionJobStatus


class RegisteredProjectFunctionJobWithStatus(
    RegisteredProjectFunctionJob, RegisteredFunctionJobWithStatusBase
):
    pass


class RegisteredSolverFunctionJobWithStatus(
    RegisteredSolverFunctionJob, RegisteredFunctionJobWithStatusBase
):
    pass


class RegisteredPythonCodeFunctionJobWithStatus(
    RegisteredPythonCodeFunctionJob, RegisteredFunctionJobWithStatusBase
):
    pass


RegisteredFunctionJobWithStatus: TypeAlias = Annotated[
    RegisteredProjectFunctionJobWithStatus
    | RegisteredPythonCodeFunctionJobWithStatus
    | RegisteredSolverFunctionJobWithStatus,
    Field(discriminator="function_class"),
]


class FunctionJobCollection(BaseModel):
    """Model for a collection of function jobs"""

    title: str = ""
    description: str = ""
    job_ids: list[FunctionJobID] = []


class RegisteredFunctionJobCollection(FunctionJobCollection):
    uid: FunctionJobCollectionID
    created_at: datetime.datetime


class FunctionJobCollectionStatus(BaseModel):
    status: list[str]


class FunctionJobDB(BaseModel):
    function_uuid: FunctionID
    title: str = ""
    description: str = ""
    inputs: FunctionInputs
    outputs: FunctionOutputs
    class_specific_data: FunctionJobClassSpecificData
    function_class: FunctionClass

    model_config = ConfigDict(from_attributes=True)


class RegisteredFunctionJobDB(FunctionJobDB):
    uuid: FunctionJobID
    created: datetime.datetime


class BatchGetCachedRegisteredFunctionJobsDB(
    BatchGetEnvelope[RegisteredFunctionJobDB, FunctionInputs]
):
    pass


class BatchCreateRegisteredFunctionJobsDB(BatchCreateEnvelope[RegisteredFunctionJobDB]):
    pass


class BatchUpdateRegisteredFunctionJobsDB(BatchUpdateEnvelope[RegisteredFunctionJobDB]):
    pass


class RegisteredFunctionJobWithStatusDB(FunctionJobDB):
    uuid: FunctionJobID
    created: datetime.datetime
    status: str


class FunctionDB(BaseModel):
    function_class: FunctionClass
    title: str = ""
    description: str = ""
    input_schema: FunctionInputSchema
    output_schema: FunctionOutputSchema
    default_inputs: FunctionInputs
    class_specific_data: FunctionClassSpecificData

    model_config = ConfigDict(from_attributes=True)


class RegisteredFunctionDB(FunctionDB):
    uuid: FunctionID
    created: datetime.datetime
    modified: datetime.datetime


class FunctionJobCollectionDB(BaseModel):
    title: str = ""
    description: str = ""

    model_config = ConfigDict(from_attributes=True)


class RegisteredFunctionJobCollectionDB(FunctionJobCollectionDB):
    uuid: FunctionJobCollectionID
    created: datetime.datetime


class FunctionIDString(ConstrainedStr):
    pattern = UUID_RE_BASE


class FunctionJobCollectionsListFilters(BaseModel):
    """Filters for listing function job collections"""

    has_function_id: FunctionIDString | None = None


class FunctionAccessRights(BaseModel):
    read: bool = False
    write: bool = False
    execute: bool = False

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class FunctionUserAccessRights(FunctionAccessRights):
    user_id: UserID


class FunctionGroupAccessRights(FunctionAccessRights):
    group_id: GroupID


class FunctionAccessRightsDB(BaseModel):
    group_id: GroupID | None = None
    product_name: ProductName | None = None
    read: bool = False
    write: bool = False
    execute: bool = False

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class FunctionUserApiAccessRights(BaseModel):
    user_id: UserID
    read_functions: bool = False
    write_functions: bool = False
    execute_functions: bool = False
    read_function_jobs: bool = False
    write_function_jobs: bool = False
    execute_function_jobs: bool = False
    read_function_job_collections: bool = False
    write_function_job_collections: bool = False
    execute_function_job_collections: bool = False

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


FunctionJobAccessRights: TypeAlias = FunctionAccessRights
FunctionJobAccessRightsDB: TypeAlias = FunctionAccessRightsDB
FunctionJobUserAccessRights: TypeAlias = FunctionUserAccessRights
FunctionJobGroupAccessRights: TypeAlias = FunctionGroupAccessRights

FunctionJobCollectionAccessRights: TypeAlias = FunctionAccessRights
FunctionJobCollectionAccessRightsDB: TypeAlias = FunctionAccessRightsDB
FunctionJobCollectionUserAccessRights: TypeAlias = FunctionUserAccessRights
FunctionJobCollectionGroupAccessRights: TypeAlias = FunctionGroupAccessRights


class FunctionsApiAccessRights(StrAutoEnum):
    READ_FUNCTIONS = "read_functions"
    WRITE_FUNCTIONS = "write_functions"
    EXECUTE_FUNCTIONS = "execute_functions"
    READ_FUNCTION_JOBS = "read_function_jobs"
    WRITE_FUNCTION_JOBS = "write_function_jobs"
    EXECUTE_FUNCTION_JOBS = "execute_function_jobs"
    READ_FUNCTION_JOB_COLLECTIONS = "read_function_job_collections"
    WRITE_FUNCTION_JOB_COLLECTIONS = "write_function_job_collections"
    EXECUTE_FUNCTION_JOB_COLLECTIONS = "execute_function_job_collections"
