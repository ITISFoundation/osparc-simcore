from models_library.functions import (
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredPythonCodeFunction,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
)

from ...api.dependencies.authentication import Identity
from ...models.api_resources import JobLinks
from ...models.domain.functions import PreRegisteredFunctionJobData
from ...models.schemas.jobs import JobInputs, JobPricingSpecification

pydantic_types_to_register = (
    Identity,
    JobInputs,
    JobLinks,
    JobPricingSpecification,
    PreRegisteredFunctionJobData,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredPythonCodeFunction,
    RegisteredProjectFunctionJob,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
)
