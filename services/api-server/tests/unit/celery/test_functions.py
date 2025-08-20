import inspect
from collections.abc import Callable

import pytest
from celery import Celery, Task
from celery.contrib.testing.worker import TestWorkController
from celery_library.task import register_task
from faker import Faker
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionJobID,
    RegisteredFunction,
    RegisteredProjectFunctionJob,
)
from models_library.projects import ProjectID
from servicelib.celery.models import TaskID
from simcore_service_api_server.api.dependencies.authentication import Identity
from simcore_service_api_server.celery._worker_tasks._functions_tasks import (
    run_function as run_function_task,
)
from simcore_service_api_server.models.api_resources import JobLinks
from simcore_service_api_server.models.schemas.jobs import (
    JobPricingSpecification,
    NodeID,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]

_faker = Faker()


def _register_fake_run_function_task() -> Callable[[Celery], None]:

    async def run_function(
        task: Task,
        task_id: TaskID,
        *,
        user_identity: Identity,
        function: RegisteredFunction,
        function_inputs: FunctionInputs,
        pricing_spec: JobPricingSpecification | None,
        job_links: JobLinks,
        x_simcore_parent_project_uuid: NodeID | None,
        x_simcore_parent_node_id: NodeID | None,
    ):
        return RegisteredProjectFunctionJob(
            title=_faker.sentence(),
            description=_faker.paragraph(),
            function_uid=FunctionID(_faker.uuid4()),
            inputs=function_inputs,
            outputs=None,
            function_class=FunctionClass.PROJECT,
            uid=FunctionJobID(_faker.uuid4()),
            created_at=_faker.date_time(),
            project_job_id=ProjectID(_faker.uuid4()),
        )

    # check our mock task is correct
    assert run_function_task.__name__ == run_function.__name__
    assert inspect.signature(run_function_task) == inspect.signature(
        run_function
    ), f"Signature mismatch: {inspect.signature(run_function_task)} != {inspect.signature(run_function)}"

    def _(celery_app: Celery) -> None:
        register_task(celery_app, run_function)

    return _


@pytest.mark.parametrize("register_celery_tasks", [_register_fake_run_function_task()])
@pytest.mark.parametrize("add_worker_tasks", [False])
async def test_with_fake_run_function(with_storage_celery_worker: TestWorkController):
    pass
