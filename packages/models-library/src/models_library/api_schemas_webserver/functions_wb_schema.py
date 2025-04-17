from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from models_library import projects
from pydantic import BaseModel, Field

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
    python_code = "python_code"


FunctionClassSpecificData: TypeAlias = dict[str, Any]
FunctionJobClassSpecificData: TypeAlias = FunctionClassSpecificData


# TODO, use InputTypes here, but api is throwing weird errors and asking for dict for elements  # noqa: FIX002
FunctionInputs: TypeAlias = dict[str, Any] | None

FunctionInputsList: TypeAlias = list[FunctionInputs]

FunctionOutputs: TypeAlias = dict[str, Any] | None


class FunctionBase(BaseModel):
    uid: FunctionID | None = None
    title: str | None = None
    description: str | None = None
    function_class: FunctionClass
    input_schema: FunctionInputSchema | None = None
    output_schema: FunctionOutputSchema | None = None


class FunctionDB(BaseModel):
    uuid: FunctionJobID | None = None
    title: str | None = None
    description: str | None = None
    function_class: FunctionClass
    input_schema: FunctionInputSchema | None = None
    output_schema: FunctionOutputSchema | None = None
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


class PythonCodeFunction(FunctionBase):
    function_class: Literal[FunctionClass.python_code] = FunctionClass.python_code
    code_url: str


Function: TypeAlias = Annotated[
    ProjectFunction | PythonCodeFunction,
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


class PythonCodeFunctionJob(FunctionJobBase):
    function_class: Literal[FunctionClass.python_code] = FunctionClass.python_code
    code_url: str


FunctionJob: TypeAlias = Annotated[
    ProjectFunctionJob | PythonCodeFunctionJob,
    Field(discriminator="function_class"),
]


class FunctionJobStatus(BaseModel):
    status: str


class FunctionJobCollection(BaseModel):
    """Model for a collection of function jobs"""

    id: FunctionJobCollectionID
    title: str | None
    description: str | None
    job_ids: list[FunctionJobID]
    status: str


class FunctionJobCollectionStatus(BaseModel):
    status: list[str]
