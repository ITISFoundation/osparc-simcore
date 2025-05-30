# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from collections.abc import AsyncIterator

import pytest
from aiohttp.test_utils import TestClient
from models_library.products import ProductName
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver.functions import (
    functions_rpc_interface as functions_rpc,
)


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,  # WARNING: AFTER env_devel_dict because HOST are set to 127.0.0.1 in here
            "WEBSERVER_FUNCTIONS": "1",
        },
    )


@pytest.fixture
async def other_logged_user(
    client: TestClient, rpc_client: RabbitMQRPCClient
) -> AsyncIterator[UserInfoDict]:
    async with LoggedUser(client) as other_user:
        yield other_user


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
