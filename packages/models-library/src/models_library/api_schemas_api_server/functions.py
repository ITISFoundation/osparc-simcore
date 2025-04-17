from typing import Annotated, Any, Literal, TypeAlias

from models_library import projects
from pydantic import BaseModel, Field

FunctionID: TypeAlias = projects.ProjectID


class FunctionSchema(BaseModel):
    schema_dict: dict[str, Any] | None  # JSON Schema


class FunctionInputSchema(FunctionSchema): ...


class FunctionOutputSchema(FunctionSchema): ...


class Function(BaseModel):
    uid: FunctionID | None = None
    title: str | None = None
    description: str | None = None
    input_schema: FunctionInputSchema | None = None
    output_schema: FunctionOutputSchema | None = None

    # @classmethod
    # def compose_resource_name(cls, function_key) -> api_resources.RelativeResourceName:
    #     return api_resources.compose_resource_name("functions", function_key)


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
