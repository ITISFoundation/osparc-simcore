from typing import Annotated

from models_library.functions import (
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
    RegisteredPythonCodeFunction,
    RegisteredSolverFunction,
    RegisteredSolverFunctionJob,
)
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import Field, StringConstraints
from servicelib.celery.models import TaskOwnerMetadata

from ..._meta import APP_NAME
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


class ApiWorkerTaskFilter(TaskOwnerMetadata):
    user_id: UserID
    product_name: ProductName
    task_owner: Annotated[
        str, StringConstraints(pattern=rf"^{APP_NAME}$"), Field(frozen=True)
    ] = APP_NAME
