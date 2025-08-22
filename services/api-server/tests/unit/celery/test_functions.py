import inspect
from collections.abc import Callable

import pytest
from celery import Celery, Task
from celery.contrib.testing.worker import TestWorkController
from celery_library.task import register_task
from celery_library.types import register_pydantic_types
from faker import Faker
from fastapi import FastAPI, status
from httpx import AsyncClient, BasicAuth, HTTPStatusError
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobFilter
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionJobID,
    RegisteredFunction,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
)
from models_library.projects import ProjectID
from servicelib.celery.models import TaskFilter, TaskID, TaskMetadata, TasksQueue
from servicelib.common_headers import (
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
)
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.api.dependencies.authentication import Identity
from simcore_service_api_server.api.dependencies.celery import (
    ASYNC_JOB_CLIENT_NAME,
    get_task_manager,
)
from simcore_service_api_server.api.routes.functions_routes import get_function
from simcore_service_api_server.celery.worker_tasks.functions_tasks import (
    run_function as run_function_task,
)
from simcore_service_api_server.exceptions.backend_errors import BaseBackEndError
from simcore_service_api_server.models.api_resources import JobLinks
from simcore_service_api_server.models.schemas.jobs import (
    JobPricingSpecification,
    NodeID,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]

_faker = Faker()


async def poll_task_until_done(
    client: AsyncClient,
    auth: BasicAuth,
    task_id: str,
    timeout: float = 30.0,
) -> TaskResult:

    async for attempt in AsyncRetrying(
        stop=stop_after_delay(timeout),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:

            response = await client.get(f"/{API_VTAG}/tasks/{task_id}", auth=auth)
            response.raise_for_status()
            status = TaskStatus.model_validate(response.json())
            assert status.done is True

    assert status.done is True
    response = await client.get(f"/{API_VTAG}/tasks/{task_id}/result", auth=auth)
    response.raise_for_status()
    return TaskResult.model_validate(response.json())


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
        register_pydantic_types(RegisteredProjectFunctionJob)
        register_task(celery_app, run_function)

    return _


@pytest.mark.parametrize("register_celery_tasks", [_register_fake_run_function_task()])
@pytest.mark.parametrize("add_worker_tasks", [False])
async def test_with_fake_run_function(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    with_api_server_celery_worker: TestWorkController,
):
    app.dependency_overrides[get_function] = (
        lambda: RegisteredProjectFunction.model_validate(
            RegisteredProjectFunction.model_config.get("json_schema_extra", {}).get(
                "examples", []
            )[0]
        )
    )

    headers = {}
    headers[X_SIMCORE_PARENT_PROJECT_UUID] = "null"
    headers[X_SIMCORE_PARENT_NODE_ID] = "null"

    body = {
        "input_1": _faker.uuid4(),
        "input_2": _faker.pyfloat(min_value=0, max_value=100),
        "input_3": _faker.pyint(min_value=0, max_value=100),
        "input_4": _faker.boolean(),
        "input_5": _faker.sentence(),
        "input_6": [
            _faker.pyfloat(min_value=0, max_value=100)
            for _ in range(_faker.pyint(min_value=5, max_value=100))
        ],
    }

    response = await client.post(
        f"/{API_VTAG}/functions/{_faker.uuid4()}:run",
        auth=auth,
        json=body,
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    task = TaskGet.model_validate(response.json())

    # Poll until task completion and get result
    result = await poll_task_until_done(client, auth, task.task_id)
    RegisteredProjectFunctionJob.model_validate(result.result)


def _register_exception_task(exception: Exception) -> Callable[[Celery], None]:

    async def exception_task(
        task: Task,
        task_id: TaskID,
    ):
        raise exception

    def _(celery_app: Celery) -> None:
        register_task(celery_app, exception_task)

    return _


@pytest.mark.parametrize(
    "register_celery_tasks",
    [
        _register_exception_task(ValueError("Test error")),
        _register_exception_task(Exception("Test error")),
        _register_exception_task(BaseBackEndError()),
    ],
)
@pytest.mark.parametrize("add_worker_tasks", [False])
async def test_celery_error_propagation(
    app: FastAPI,
    client: AsyncClient,
    auth: BasicAuth,
    with_api_server_celery_worker: TestWorkController,
):

    user_identity = Identity(
        user_id=_faker.pyint(), product_name=_faker.word(), email=_faker.email()
    )
    job_filter = AsyncJobFilter(
        user_id=user_identity.user_id,
        product_name=user_identity.product_name,
        client_name=ASYNC_JOB_CLIENT_NAME,
    )
    task_manager = get_task_manager(app=app)
    task_uuid = await task_manager.submit_task(
        task_metadata=TaskMetadata(
            name="exception_task", queue=TasksQueue.API_WORKER_QUEUE
        ),
        task_filter=TaskFilter.model_validate(job_filter.model_dump()),
    )

    with pytest.raises(HTTPStatusError) as exc_info:
        await poll_task_until_done(client, auth, f"{task_uuid}")

    assert exc_info.value.response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
