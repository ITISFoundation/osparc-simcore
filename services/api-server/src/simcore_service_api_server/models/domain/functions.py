from models_library.functions import FunctionJobID
from pydantic import BaseModel

from ...models.schemas.jobs import JobInputs


class PreRegisteredFunctionJobData(BaseModel):
    function_job_id: FunctionJobID
    job_inputs: JobInputs
