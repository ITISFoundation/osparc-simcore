from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias

from models_library import projects
from pydantic import BaseModel, Field

FunctionID: TypeAlias = projects.ProjectID


class FunctionSchema(BaseModel):
    schema_dict: dict[str, Any] | None  # JSON Schema


class FunctionInputSchema(FunctionSchema): ...


class FunctionOutputSchema(FunctionSchema): ...


class FunctionClass(str, Enum):
    project = "project"
    python_code = "python_code"


class FunctionInputs(BaseModel):
    inputs_dict: dict[str, Any] | None  # JSON Schema


class FunctionOutputs(BaseModel):
    outputs_dict: dict[str, Any] | None  # JSON Schema


class Function(BaseModel):
    uid: FunctionID | None = None
    title: str | None = None
    description: str | None = None
    input_schema: FunctionInputSchema | None = None
    output_schema: FunctionOutputSchema | None = None


class StudyFunction(Function):
    function_type: Literal["study"] = "study"
    study_url: str


class PythonCodeFunction(Function):
    function_type: Literal["python_code"] = "python_code"
    code_url: str


FunctionUnion: TypeAlias = Annotated[
    StudyFunction | PythonCodeFunction,
    Field(discriminator="function_type"),
]

FunctionJobID: TypeAlias = projects.ProjectID
FunctionJobCollectionID: TypeAlias = projects.ProjectID


class FunctionJob(BaseModel):
    uid: FunctionJobID
    title: str | None
    description: str | None
    status: str
    function_uid: FunctionID
    inputs: FunctionInputs | None
    outputs: FunctionOutputs | None


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
