import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
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
    FunctionUserAccessRights,
    FunctionUserApiAccessRights,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
)
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_mock import MockType
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
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


@pytest.mark.parametrize(
    "parent_project_uuid, parent_node_uuid, expected_status_code",
    [
        (None, None, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (f"{_faker.uuid4()}", None, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (None, f"{_faker.uuid4()}", status.HTTP_422_UNPROCESSABLE_ENTITY),
        (f"{_faker.uuid4()}", f"{_faker.uuid4()}", status.HTTP_200_OK),
        ("null", "null", status.HTTP_200_OK),
    ],
)
@pytest.mark.parametrize("capture", ["run_study_function_parent_info.json"])
@pytest.mark.parametrize("mocked_app_dependencies", [None])
async def test_run_project_function_parent_info(
    app: FastAPI,
    with_api_server_celery_worker: TestWorkController,
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    mock_registered_project_function: RegisteredProjectFunction,
    mock_registered_project_function_job: RegisteredFunctionJob,
    auth: httpx.BasicAuth,
    user_id: UserID,
    mocked_webserver_rest_api_base: respx.MockRouter,
    mocked_directorv2_rest_api_base: respx.MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    create_respx_mock_from_capture,
    project_tests_dir: Path,
    parent_project_uuid: str | None,
    parent_node_uuid: str | None,
    expected_status_code: int,
    capture: str,
) -> None:
    def _default_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        if request.method == "POST" and request.url.path.endswith("/projects"):
            if parent_project_uuid and parent_project_uuid != "null":
                _parent_uuid = request.headers.get(X_SIMCORE_PARENT_PROJECT_UUID)
                assert _parent_uuid is not None
                assert parent_project_uuid == _parent_uuid
            if parent_node_uuid and parent_node_uuid != "null":
                _parent_node_uuid = request.headers.get(X_SIMCORE_PARENT_NODE_ID)
                assert _parent_node_uuid is not None
                assert parent_node_uuid == _parent_node_uuid
        return capture.response_body

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base, mocked_directorv2_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[_default_side_effect] * 50,
    )

    mock_handler_in_functions_rpc_interface(
        "get_function_user_permissions",
        FunctionUserAccessRights(
            user_id=user_id,
            execute=True,
            read=True,
            write=True,
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", mock_registered_project_function
    )
    mock_handler_in_functions_rpc_interface("find_cached_function_jobs", [])
    mock_handler_in_functions_rpc_interface(
        "register_function_job", mock_registered_project_function_job
    )
    mock_handler_in_functions_rpc_interface(
        "get_functions_user_api_access_rights",
        FunctionUserApiAccessRights(
            user_id=user_id,
            execute_functions=True,
            write_functions=True,
            read_functions=True,
        ),
    )

    headers = {}
    if parent_project_uuid:
        headers[X_SIMCORE_PARENT_PROJECT_UUID] = parent_project_uuid
    if parent_node_uuid:
        headers[X_SIMCORE_PARENT_NODE_ID] = parent_node_uuid

    response = await client.post(
        f"{API_VTAG}/functions/{mock_registered_project_function.uid}:run",
        json={},
        auth=auth,
        headers=headers,
    )
    assert response.status_code == expected_status_code
    if response.status_code == status.HTTP_200_OK:
        task = TaskGet.model_validate(response.json())
        result = await poll_task_until_done(client, auth, task.task_id)
        RegisteredProjectFunctionJob.model_validate(result.result)
