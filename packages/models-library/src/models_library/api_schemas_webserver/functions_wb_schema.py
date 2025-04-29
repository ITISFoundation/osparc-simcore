from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from models_library import projects
from models_library.basic_regex import SIMPLE_VERSION_RE
from models_library.services_regex import COMPUTATIONAL_SERVICE_KEY_RE
from pydantic import BaseModel, Field, StringConstraints

from ..projects import ProjectID

FunctionID: TypeAlias = projects.ProjectID
FunctionJobID: TypeAlias = projects.ProjectID
FileID: TypeAlias = UUID

InputTypes: TypeAlias = FileID | float | int | bool | str | list | None


class FunctionSchema(BaseModel):
    schema_dict: dict[str, Any] | None  # JSON Schema


class FunctionInputSchema(FunctionSchema): ...


class FunctionOutputSchema(FunctionSchema): ...


class FunctionClass(str, Enum):
    project = "project"
    solver = "solver"
    python_code = "python_code"


FunctionClassSpecificData: TypeAlias = dict[str, Any]
FunctionJobClassSpecificData: TypeAlias = FunctionClassSpecificData


# TODO, use InputTypes here, but api is throwing weird errors and asking for dict for elements  # noqa: FIX002
FunctionInputs: TypeAlias = dict[str, Any] | None

FunctionInputsList: TypeAlias = list[FunctionInputs]

FunctionOutputs: TypeAlias = dict[str, Any] | None


class FunctionBase(BaseModel):
    function_class: FunctionClass
    uid: FunctionID | None = None
    title: str | None = None
    description: str | None = None
    input_schema: FunctionInputSchema | None = None
    output_schema: FunctionOutputSchema | None = None
    default_inputs: FunctionInputs | None = None


class FunctionDB(BaseModel):
    function_class: FunctionClass
    uuid: FunctionJobID | None = None
    title: str | None = None
    description: str | None = None
    input_schema: FunctionInputSchema | None = None
    output_schema: FunctionOutputSchema | None = None
    default_inputs: FunctionInputs | None = None
    class_specific_data: FunctionClassSpecificData


class FunctionJobDB(BaseModel):
    uuid: FunctionJobID | None = None
    function_uuid: FunctionID
    title: str | None = None
    inputs: FunctionInputs | None = None
    outputs: FunctionOutputs | None = None
    class_specific_data: FunctionJobClassSpecificData
    function_class: FunctionClass


class ProjectFunction(FunctionBase):
    function_class: Literal[FunctionClass.project] = FunctionClass.project
    project_id: ProjectID


SolverKeyId = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=COMPUTATIONAL_SERVICE_KEY_RE)
]
VersionStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=SIMPLE_VERSION_RE)
]
SolverJobID: TypeAlias = UUID


class SolverFunction(FunctionBase):
    function_class: Literal[FunctionClass.solver] = FunctionClass.solver
    solver_key: SolverKeyId
    solver_version: str


class PythonCodeFunction(FunctionBase):
    function_class: Literal[FunctionClass.python_code] = FunctionClass.python_code
    code_url: str


Function: TypeAlias = Annotated[
    ProjectFunction | PythonCodeFunction | SolverFunction,
    Field(discriminator="function_class"),
]

FunctionJobCollectionID: TypeAlias = projects.ProjectID


class FunctionJobBase(BaseModel):
    uid: FunctionJobID | None = None
    title: str | None = None
    description: str | None = None
    function_uid: FunctionID
    inputs: FunctionInputs | None = None
    outputs: FunctionOutputs | None = None
    function_class: FunctionClass


class ProjectFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.project] = FunctionClass.project
    project_job_id: ProjectID


class SolverFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.solver] = FunctionClass.solver
    solver_job_id: ProjectID


class PythonCodeFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.python_code] = FunctionClass.python_code


FunctionJob: TypeAlias = Annotated[
    ProjectFunctionJob | PythonCodeFunctionJob | SolverFunctionJob,
    Field(discriminator="function_class"),
]


class FunctionJobStatus(BaseModel):
    status: str


class FunctionJobCollection(BaseModel):
    """Model for a collection of function jobs"""

    uid: FunctionJobCollectionID | None
    title: str | None
    description: str | None
    job_ids: list[FunctionJobID]


class FunctionJobCollectionDB(BaseModel):
    """Model for a collection of function jobs"""

    uuid: FunctionJobCollectionID | None
    title: str | None
    description: str | None


class FunctionJobCollectionStatus(BaseModel):
    status: list[str]
