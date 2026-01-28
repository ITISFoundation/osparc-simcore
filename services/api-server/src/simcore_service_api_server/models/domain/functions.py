from models_library.functions import (
    FunctionClass,
    FunctionJobID,
    RegisteredFunctionJob,
    RegisteredFunctionJobWithStatus,
    SolverJobID,
    TaskID,
)
from models_library.projects import ProjectID
from pydantic import BaseModel, model_validator

from ...models.pagination import Page
from ...models.schemas.jobs import JobInputs


class PreRegisteredFunctionJobData(BaseModel):
    function_job_id: FunctionJobID
    job_inputs: JobInputs


class PageRegisteredFunctionJobWithorWithoutStatus(
    Page[RegisteredFunctionJobWithStatus | RegisteredFunctionJob]  # order is important
):
    # This class is created specifically to provide a name for this in openapi.json.
    # When using an alias the python-client generates too long file name
    pass


class FunctionJobPatch(BaseModel):
    function_class: FunctionClass
    function_job_id: FunctionJobID
    job_creation_task_id: TaskID | None = None
    project_job_id: ProjectID | None = None
    solver_job_id: SolverJobID | None = None

    @model_validator(mode="after")
    def validate_function_class_consistency(self) -> "FunctionJobPatch":
        """Validate consistency between function_class and job IDs."""
        if self.solver_job_id is not None and self.function_class != FunctionClass.SOLVER:
            msg = f"solver_job_id must be None when function_class is {self.function_class}, expected {FunctionClass.SOLVER}"
            raise ValueError(msg)

        if self.project_job_id is not None and self.function_class != FunctionClass.PROJECT:
            msg = f"project_job_id must be None when function_class is {self.function_class}, expected {FunctionClass.PROJECT}"
            raise ValueError(msg)

        return self
