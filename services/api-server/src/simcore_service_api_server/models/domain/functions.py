from models_library.functions import (
    FunctionJobID,
    RegisteredFunctionJob,
    RegisteredFunctionJobWithStatus,
)
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
