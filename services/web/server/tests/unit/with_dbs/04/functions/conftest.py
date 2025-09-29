# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any
from uuid import UUID, uuid4

import pytest
import sqlalchemy
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.functions import (
    Function,
    JSONFunctionInputSchema,
    JSONFunctionOutputSchema,
    ProjectFunction,
)
from models_library.functions import FunctionClass, SolverFunction
from models_library.products import ProductName
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver.functions import (
    functions_rpc_interface as functions_rpc,
)
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.funcapi_api_access_rights_table import (
    funcapi_api_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_jobs_table import (
    function_jobs_table,
)
from simcore_postgres_database.models.funcapi_functions_access_rights_table import (
    functions_access_rights_table,
)
from simcore_postgres_database.models.funcapi_functions_table import functions_table
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.statics._constants import FRONTEND_APP_DEFAULT
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(scope="session")
def service_name() -> str:
    # Overrides  service_name fixture needed in docker_compose_service_environment_dict fixture
    return "wb-api-server"


@pytest.fixture
def app_environment(
    rabbit_service: RabbitSettings,
    app_environment: EnvVarsDict,
    docker_compose_service_environment_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    new_envs = setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            **app_environment,
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            "WEBSERVER_FUNCTIONS": "1",
        },
    )

    settings = ApplicationSettings.create_from_envs()
    assert settings.WEBSERVER_RABBITMQ

    return new_envs


@pytest.fixture
async def rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


@pytest.fixture
def mock_function_factory() -> Callable[[FunctionClass], Function]:
    def _(function_class: FunctionClass) -> Function:
        if function_class == FunctionClass.PROJECT:
            return ProjectFunction(
                title="Test Function",
                description="A test function",
                input_schema=JSONFunctionInputSchema(
                    schema_content={
                        "type": "object",
                        "properties": {"input1": {"type": "string"}},
                    }
                ),
                output_schema=JSONFunctionOutputSchema(
                    schema_content={
                        "type": "object",
                        "properties": {"output1": {"type": "string"}},
                    }
                ),
                project_id=uuid4(),
                default_inputs=None,
            )
        if function_class == FunctionClass.SOLVER:
            return SolverFunction(
                title="Test Solver",
                description="A test solver",
                input_schema=JSONFunctionInputSchema(
                    schema_content={
                        "type": "object",
                        "properties": {"input1": {"type": "string"}},
                    }
                ),
                output_schema=JSONFunctionOutputSchema(
                    schema_content={
                        "type": "object",
                        "properties": {"output1": {"type": "string"}},
                    }
                ),
                default_inputs=None,
                solver_key="simcore/services/comp/mysolver",
                solver_version="1.0.0",
            )
        msg = f"Please implement the mock for {function_class=} yourself"
        raise AssertionError(msg)

    return _


@pytest.fixture
async def other_logged_user(
    client: TestClient, rpc_client: RabbitMQRPCClient
) -> AsyncIterator[UserInfoDict]:
    async with LoggedUser(client) as other_user:
        yield other_user


@pytest.fixture
async def user_without_function_api_access_rights(
    client: TestClient, rpc_client: RabbitMQRPCClient
) -> AsyncIterator[UserInfoDict]:
    async with LoggedUser(client) as user_without_function_api_access_rights:
        yield user_without_function_api_access_rights


@pytest.fixture
async def clean_functions(
    client: TestClient,
    rpc_client: RabbitMQRPCClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
) -> None:
    assert client.app

    functions, _ = await functions_rpc.list_functions(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=100,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    for function in functions:
        assert function.uid is not None
        await functions_rpc.delete_function(
            rabbitmq_rpc_client=rpc_client,
            function_id=function.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.fixture
async def clean_function_job_collections(
    client: TestClient,
    rpc_client: RabbitMQRPCClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
) -> None:
    assert client.app

    job_collections, _ = await functions_rpc.list_function_job_collections(
        rabbitmq_rpc_client=rpc_client,
        pagination_limit=100,
        pagination_offset=0,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    for function_job_collection in job_collections:
        assert function_job_collection.uid is not None
        await functions_rpc.delete_function_job_collection(
            rabbitmq_rpc_client=rpc_client,
            function_job_collection_id=function_job_collection.uid,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
        )


@pytest.fixture
async def add_user_function_api_access_rights(
    asyncpg_engine: AsyncEngine,
    logged_user: UserInfoDict,
    other_logged_user: UserInfoDict,
    request: pytest.FixtureRequest,
) -> AsyncIterator[None]:
    if hasattr(request, "param") and not request.param:
        yield
        return
    async with asyncpg_engine.begin() as conn:
        for group_id in (logged_user["primary_gid"], other_logged_user["primary_gid"]):
            await conn.execute(
                funcapi_api_access_rights_table.insert().values(
                    group_id=group_id,
                    product_name=FRONTEND_APP_DEFAULT,
                    read_functions=True,
                    write_functions=True,
                    execute_functions=True,
                    read_function_jobs=True,
                    write_function_jobs=True,
                    execute_function_jobs=True,
                    read_function_job_collections=True,
                    write_function_job_collections=True,
                    execute_function_job_collections=True,
                )
            )
    yield
    async with asyncpg_engine.begin() as conn:
        for group_id in (logged_user["primary_gid"], other_logged_user["primary_gid"]):
            await conn.execute(
                sqlalchemy.delete(funcapi_api_access_rights_table).where(
                    funcapi_api_access_rights_table.c.group_id == group_id
                )
            )


@pytest.fixture
async def logged_user_function_api_access_rights(
    asyncpg_engine: AsyncEngine,
    logged_user: UserInfoDict,
    *,
    expected_read_functions: bool,
    expected_write_functions: bool,
) -> AsyncIterator[dict[str, Any]]:
    cm = insert_and_get_row_lifespan(
        asyncpg_engine,
        table=funcapi_api_access_rights_table,
        values={
            "group_id": logged_user["primary_gid"],
            "product_name": FRONTEND_APP_DEFAULT,
            "read_functions": expected_read_functions,
            "write_functions": expected_write_functions,
            "execute_functions": True,
            "read_function_jobs": True,
            "write_function_jobs": True,
            "execute_function_jobs": True,
            "read_function_job_collections": True,
            "write_function_job_collections": True,
            "execute_function_job_collections": True,
        },
        pk_col=funcapi_api_access_rights_table.c.group_id,
        pk_value=logged_user["primary_gid"],
    )

    async with AsyncExitStack() as stack:
        row = await stack.enter_async_context(cm)
        yield row


@pytest.fixture
async def fake_function_with_associated_job(
    asyncpg_engine: AsyncEngine,
    logged_user: UserInfoDict,
) -> AsyncIterator[UUID]:
    async with AsyncExitStack() as stack:
        function_row = await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=functions_table,
                values={
                    "title": "Test Function",
                    "function_class": FunctionClass.PROJECT.value,
                    "description": "A test function",
                    "input_schema": {
                        "schema_class": "application/schema+json",
                        "schema_content": {
                            "type": "object",
                            "properties": {"input1": {"type": "string"}},
                        },
                    },
                    "output_schema": {
                        "schema_class": "application/schema+json",
                        "schema_content": {
                            "type": "object",
                            "properties": {"output1": {"type": "string"}},
                        },
                    },
                    "class_specific_data": {"project_id": f"{uuid4()}"},
                },
                pk_col=functions_table.c.uuid,
            )
        )

        await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=functions_access_rights_table,
                values={
                    "function_uuid": function_row["uuid"],
                    "group_id": logged_user["primary_gid"],
                    "product_name": "osparc",  # Default product name
                    "read": True,
                    "write": True,
                    "execute": True,
                },
                pk_cols=[
                    functions_access_rights_table.c.function_uuid,
                    functions_access_rights_table.c.group_id,
                    functions_access_rights_table.c.product_name,
                ],
            )
        )

        await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=function_jobs_table,
                values={
                    "function_uuid": function_row["uuid"],
                    "status": "pending",
                },
                pk_col=function_jobs_table.c.uuid,
            )
        )
        yield function_row["uuid"]
