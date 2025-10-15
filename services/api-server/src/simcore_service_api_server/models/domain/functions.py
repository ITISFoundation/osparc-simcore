from typing import NamedTuple

from models_library.functions import (
    FunctionClass,
    FunctionJobID,
    RegisteredFunctionJob,
    RegisteredFunctionJobWithStatus,
    SolverJobID,
    TaskID,
)
from models_library.projects import ProjectID
from pydantic import BaseModel

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


class ProjectFunctionJobPatch(NamedTuple):
    function_class = FunctionClass.PROJECT
    function_job_id: FunctionJobID
    job_creation_task_id: TaskID | None
    project_job_id: ProjectID | None


class SolverFunctionJobPatch(NamedTuple):
    function_class = FunctionClass.SOLVER
    function_job_id: FunctionJobID
    job_creation_task_id: TaskID | None
    solver_job_id: SolverJobID | None
