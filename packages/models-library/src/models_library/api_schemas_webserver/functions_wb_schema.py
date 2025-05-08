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

InputTypes: TypeAlias = FileID | float | int | bool | str | list


class FunctionSchema(BaseModel):
    """Schema for function input/output"""

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

FunctionOutputsLogfile: TypeAlias = Any


class FunctionBase(BaseModel):
    function_class: FunctionClass
    uid: FunctionID | None
    title: str = ""
    description: str = ""
    input_schema: FunctionInputSchema | None
    output_schema: FunctionOutputSchema | None
    default_inputs: FunctionInputs


class FunctionDB(BaseModel):
    function_class: FunctionClass
    uuid: FunctionJobID | None
    title: str = ""
    description: str = ""
    input_schema: FunctionInputSchema | None
    output_schema: FunctionOutputSchema | None
    default_inputs: FunctionInputs
    class_specific_data: FunctionClassSpecificData


class FunctionJobDB(BaseModel):
    uuid: FunctionJobID | None
    function_uuid: FunctionID
    title: str = ""
    inputs: FunctionInputs
    outputs: FunctionOutputs
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
    solver_version: str = ""


class PythonCodeFunction(FunctionBase):
    function_class: Literal[FunctionClass.python_code] = FunctionClass.python_code
    code_url: str


Function: TypeAlias = Annotated[
    ProjectFunction | PythonCodeFunction | SolverFunction,
    Field(discriminator="function_class"),
]

FunctionJobCollectionID: TypeAlias = projects.ProjectID


class FunctionJobBase(BaseModel):
    uid: FunctionJobID | None
    title: str = ""
    description: str = ""
    function_uid: FunctionID
    inputs: FunctionInputs
    outputs: FunctionOutputs
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
    title: str = ""
    description: str = ""
    job_ids: list[FunctionJobID]


class FunctionJobCollectionDB(BaseModel):
    """Model for a collection of function jobs"""

    uuid: FunctionJobCollectionID
    title: str = ""
    description: str = ""


class FunctionJobCollectionStatus(BaseModel):
    status: list[str]


class FunctionNotFoundError(Exception):
    """Exception raised when a function is not found"""

    def __init__(self, function_id: FunctionID):
        self.function_id = function_id
        super().__init__(f"Function {function_id} not found")


class FunctionJobNotFoundError(Exception):
    """Exception raised when a function job is not found"""

    def __init__(self, function_job_id: FunctionJobID):
        self.function_job_id = function_job_id
        super().__init__(f"Function job {function_job_id} not found")


class FunctionJobCollectionNotFoundError(Exception):
    """Exception raised when a function job collection is not found"""

    def __init__(self, function_job_collection_id: FunctionJobCollectionID):
        self.function_job_collection_id = function_job_collection_id
        super().__init__(
            f"Function job collection {function_job_collection_id} not found"
        )


class RegisterFunctionWithUIDError(Exception):
    """Exception raised when registering a function with a UID"""

    def __init__(self):
        super().__init__("Cannot register Function with a UID")


class UnsupportedFunctionClassError(Exception):
    """Exception raised when a function class is not supported"""

    def __init__(self, function_class: str):
        self.function_class = function_class
        super().__init__(f"Function class {function_class} is not supported")


class UnsupportedFunctionJobClassError(Exception):
    """Exception raised when a function job class is not supported"""

    def __init__(self, function_job_class: str):
        self.function_job_class = function_job_class
        super().__init__(f"Function job class {function_job_class} is not supported")
