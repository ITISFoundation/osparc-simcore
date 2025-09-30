# pylint: disable=unused-argument
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=redefined-outer-name

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
import respx
from celery import Task  # pylint: disable=no-name-in-module
from celery_library.task_manager import CeleryTaskManager
from faker import Faker
from fastapi import FastAPI
from httpx import AsyncClient
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.functions import (
    FunctionUserAccessRights,
    FunctionUserApiAccessRights,
    ProjectFunction,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredProjectFunction,
    RegisteredProjectFunctionJob,
)
from models_library.functions_errors import (
    FunctionIDNotFoundError,
    FunctionReadAccessDeniedError,
)
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from pydantic import EmailStr
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.httpx_calls_capture_models import HttpApiCallCaptureModel
from servicelib.aiohttp import status
from servicelib.celery.app_server import BaseAppServer
from servicelib.celery.models import TaskID
from servicelib.common_headers import (
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
)
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.api.dependencies.authentication import Identity
from simcore_service_api_server.celery_worker.worker_tasks import functions_tasks
from simcore_service_api_server.models.api_resources import JobLinks
from simcore_service_api_server.models.domain.functions import (
    PreRegisteredFunctionJobData,
)
from simcore_service_api_server.models.schemas.jobs import JobInputs
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient

_faker = Faker()


async def test_register_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], MockType],
    fake_function: ProjectFunction,
    auth: httpx.BasicAuth,
    fake_registered_project_function: RegisteredProjectFunction,
) -> None:
    mock = mock_handler_in_functions_rpc_interface(
        "register_function", fake_registered_project_function
    )
    response = await client.post(
        f"{API_VTAG}/functions", json=fake_function.model_dump(mode="json"), auth=auth
    )

    assert mock.called
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    returned_function = RegisteredProjectFunction.model_validate(data)
    assert returned_function.uid is not None
    assert returned_function == fake_registered_project_function


async def test_register_function_invalid(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    auth: httpx.BasicAuth,
) -> None:
    invalid_function = {
        "title": "test_function",
        "function_class": "invalid_class",  # Invalid class
        "project_id": str(uuid4()),
    }
    response = await client.post(
        f"{API_VTAG}/functions", json=invalid_function, auth=auth
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert (
        "Input tag 'invalid_class' found using 'function_class' does not"
        in response.json()["errors"][0]["msg"]
    )


async def test_get_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    function_id = str(uuid4())

    mock_handler_in_functions_rpc_interface(
        "get_function", fake_registered_project_function
    )
    response = await client.get(f"{API_VTAG}/functions/{function_id}", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    returned_function = RegisteredProjectFunction.model_validate(response.json())
    assert returned_function == fake_registered_project_function


async def test_get_function_not_found(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[
        [str, Any, Exception | None], None
    ],
    auth: httpx.BasicAuth,
) -> None:
    non_existent_function_id = str(uuid4())

    mock_handler_in_functions_rpc_interface(
        "get_function",
        None,
        FunctionIDNotFoundError(function_id=non_existent_function_id),
    )
    response = await client.get(
        f"{API_VTAG}/functions/{non_existent_function_id}", auth=auth
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_function_read_access_denied(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[
        [str, Any, Exception | None], None
    ],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    unauthorized_user_id = "unauthorized user"
    mock_handler_in_functions_rpc_interface(
        "get_function",
        None,
        FunctionReadAccessDeniedError(
            function_id=fake_registered_project_function.uid,
            user_id=unauthorized_user_id,
        ),
    )
    response = await client.get(
        f"{API_VTAG}/functions/{fake_registered_project_function.uid}", auth=auth
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["errors"][0] == (
        f"Function {fake_registered_project_function.uid} read access denied for user {unauthorized_user_id}"
    )


async def test_list_functions(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "list_functions",
        (
            [fake_registered_project_function for _ in range(5)],
            PageMetaInfoLimitOffset(total=5, count=5, limit=10, offset=0),
        ),
    )

    response = await client.get(
        f"{API_VTAG}/functions", params={"limit": 10, "offset": 0}, auth=auth
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["items"]
    assert len(data) == 5
    assert data[0]["title"] == fake_registered_project_function.title


async def test_update_function_title(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "update_function_title",
        RegisteredProjectFunction(
            **{
                **fake_registered_project_function.model_dump(),
                "title": "updated_example_function",
            }
        ),
    )

    # Update the function title
    updated_title = {"title": "updated_example_function"}
    response = await client.patch(
        f"{API_VTAG}/functions/{fake_registered_project_function.uid}/title",
        params=updated_title,
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["title"] == updated_title["title"]


async def test_update_function_description(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "update_function_description",
        RegisteredProjectFunction(
            **{
                **fake_registered_project_function.model_dump(),
                "description": "updated_example_function",
            }
        ),
    )

    # Update the function description
    updated_description = {"description": "updated_example_function"}
    response = await client.patch(
        f"{API_VTAG}/functions/{fake_registered_project_function.uid}/description",
        params=updated_description,
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["description"] == updated_description["description"]


async def test_get_function_input_schema(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "get_function", fake_registered_project_function
    )

    response = await client.get(
        f"{API_VTAG}/functions/{fake_registered_project_function.uid}/input_schema",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert (
        data["schema_content"]
        == fake_registered_project_function.input_schema.schema_content
    )


async def test_get_function_output_schema(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "get_function", fake_registered_project_function
    )

    response = await client.get(
        f"{API_VTAG}/functions/{fake_registered_project_function.uid}/output_schema",
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert (
        data["schema_content"]
        == fake_registered_project_function.output_schema.schema_content
    )


async def test_validate_function_inputs(
    client: AsyncClient,
    mock_rabbitmq_rpc_client: MockerFixture,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface(
        "get_function", fake_registered_project_function
    )

    # Validate inputs
    validate_payload = {"input1": 10}
    response = await client.post(
        f"{API_VTAG}/functions/{fake_registered_project_function.uid}:validate_inputs",
        json=validate_payload,
        auth=auth,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == [True, "Inputs are valid"]


async def test_delete_function(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
) -> None:
    mock_handler_in_functions_rpc_interface("delete_function", None)

    # Delete the function
    response = await client.delete(
        f"{API_VTAG}/functions/{fake_registered_project_function.uid}", auth=auth
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize("user_has_execute_right", [False, True])
@pytest.mark.parametrize(
    "funcapi_endpoint,endpoint_inputs", [("run", {}), ("map", [{}, {}])]
)
async def test_run_map_function_not_allowed(
    client: AsyncClient,
    mocker: MockerFixture,
    mock_celery_task_manager: MockType,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    auth: httpx.BasicAuth,
    user_id: UserID,
    mocked_webserver_rest_api_base: respx.MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
    user_has_execute_right: bool,
    funcapi_endpoint: str,
    endpoint_inputs: dict | list[dict],
) -> None:
    """Test that running a function is not allowed."""

    mocker.patch(
        "simcore_service_api_server.api.dependencies.services.get_task_manager",
        return_value=mocker.MagicMock(spec=CeleryTaskManager),
    )

    mock_handler_in_functions_rpc_interface(
        "get_function_user_permissions",
        FunctionUserAccessRights(
            user_id=user_id,
            execute=False,
            read=True,
            write=True,
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_functions_user_api_access_rights",
        FunctionUserApiAccessRights(
            user_id=user_id,
            execute_functions=user_has_execute_right,
            write_functions=True,
            read_functions=True,
        ),
    )

    mock_handler_in_functions_rpc_interface(
        "get_function",
        fake_registered_project_function,
    )

    # Monkeypatching MagicMock because otherwise it refuse to be used in an await statement
    async def async_magic():
        pass

    MagicMock.__await__ = lambda _: async_magic().__await__()

    response = await client.post(
        f"{API_VTAG}/functions/{fake_registered_project_function.uid}:{funcapi_endpoint}",
        json=endpoint_inputs,
        auth=auth,
        headers={
            X_SIMCORE_PARENT_PROJECT_UUID: "null",
            X_SIMCORE_PARENT_NODE_ID: "null",
        },
    )
    if user_has_execute_right:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["errors"][0] == (
            f"Function {fake_registered_project_function.uid} execute access denied for user {user_id}"
        )
    else:
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["errors"][0] == (
            f"User {user_id} does not have the permission to execute functions"
        )


@pytest.mark.parametrize("capture", ["run_study_function_parent_info.json"])
async def test_run_project_function(
    mocker: MockerFixture,
    mocked_webserver_rpc_api: dict[str, MockType],
    app: FastAPI,
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredProjectFunction,
    fake_registered_project_function_job: RegisteredFunctionJob,
    auth: httpx.BasicAuth,
    user_identity: Identity,
    user_email: EmailStr,
    job_links: JobLinks,
    mocked_webserver_rest_api_base: respx.MockRouter,
    mocked_directorv2_rest_api_base: respx.MockRouter,
    create_respx_mock_from_capture,
    project_tests_dir: Path,
    capture: str,
) -> None:

    def _get_app_server(celery_app: Any) -> FastAPI:
        app_server = mocker.Mock(spec=BaseAppServer)
        app_server.app = app
        return app_server

    mocker.patch.object(functions_tasks, "get_app_server", _get_app_server)

    def _get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
        return mocker.MagicMock(spec=RabbitMQRPCClient)

    mocker.patch.object(
        functions_tasks, "get_rabbitmq_rpc_client", _get_rabbitmq_rpc_client
    )

    async def _get_wb_api_rpc_client(app: FastAPI) -> WbApiRpcClient:
        from simcore_service_api_server.services_rpc import wb_api_server

        wb_api_server.setup(app, mocker.MagicMock(spec=RabbitMQRPCClient))
        return WbApiRpcClient.get_from_app_state(app)

    mocker.patch.object(
        functions_tasks, "get_wb_api_rpc_client", _get_wb_api_rpc_client
    )

    def _default_side_effect(
        request: httpx.Request,
        path_params: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        return capture.response_body

    create_respx_mock_from_capture(
        respx_mocks=[mocked_webserver_rest_api_base, mocked_directorv2_rest_api_base],
        capture_path=project_tests_dir / "mocks" / capture,
        side_effects_callbacks=[_default_side_effect] * 50,
    )

    mock_handler_in_functions_rpc_interface(
        "get_function_user_permissions",
        FunctionUserAccessRights(
            user_id=user_identity.user_id,
            execute=True,
            read=True,
            write=True,
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "get_function", fake_registered_project_function
    )
    mock_handler_in_functions_rpc_interface("find_cached_function_jobs", [])
    mock_handler_in_functions_rpc_interface(
        "register_function_job", fake_registered_project_function_job
    )
    mock_handler_in_functions_rpc_interface(
        "get_functions_user_api_access_rights",
        FunctionUserApiAccessRights(
            user_id=user_identity.user_id,
            execute_functions=True,
            write_functions=True,
            read_functions=True,
        ),
    )
    mock_handler_in_functions_rpc_interface(
        "patch_registered_function_job", fake_registered_project_function_job
    )

    pre_registered_function_job_data = PreRegisteredFunctionJobData(
        job_inputs=JobInputs(values={}),
        function_job_id=fake_registered_project_function.uid,
    )

    job = await functions_tasks.run_function(
        task=MagicMock(spec=Task),
        task_id=TaskID(_faker.uuid4()),
        user_identity=user_identity,
        function=fake_registered_project_function,
        pre_registered_function_job_data=pre_registered_function_job_data,
        pricing_spec=None,
        job_links=job_links,
        x_simcore_parent_project_uuid=None,
        x_simcore_parent_node_id=None,
    )
    assert isinstance(job, RegisteredProjectFunctionJob)


async def test_export_logs_project_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_project_function: RegisteredFunction,
    fake_registered_project_function_job: RegisteredFunctionJob,
    mocked_directorv2_rpc_api: dict[str, MockType],
    mocked_storage_rpc_api: dict[str, MockType],
    auth: httpx.BasicAuth,
    user_id: UserID,
):
    mock_handler_in_functions_rpc_interface(
        "get_function", fake_registered_project_function
    )
    mock_handler_in_functions_rpc_interface(
        "get_function_job", fake_registered_project_function_job
    )

    response = await client.post(
        f"{API_VTAG}/function_jobs/{fake_registered_project_function_job.uid}/log",
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    TaskGet.model_validate(response.json())


async def test_export_logs_solver_function_job(
    client: AsyncClient,
    mock_handler_in_functions_rpc_interface: Callable[[str, Any], None],
    fake_registered_solver_function: RegisteredFunction,
    fake_registered_solver_function_job: RegisteredFunctionJob,
    mocked_directorv2_rpc_api: dict[str, MockType],
    mocked_storage_rpc_api: dict[str, MockType],
    auth: httpx.BasicAuth,
    user_id: UserID,
):
    mock_handler_in_functions_rpc_interface(
        "get_function", fake_registered_solver_function
    )
    mock_handler_in_functions_rpc_interface(
        "get_function_job", fake_registered_solver_function_job
    )

    response = await client.post(
        f"{API_VTAG}/function_jobs/{fake_registered_solver_function_job.uid}/log",
        auth=auth,
    )

    assert response.status_code == status.HTTP_200_OK
    TaskGet.model_validate(response.json())
