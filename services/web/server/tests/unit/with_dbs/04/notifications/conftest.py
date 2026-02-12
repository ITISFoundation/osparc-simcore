# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager

import pytest
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from simcore_service_webserver.notifications import _service


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # Override app_environment to enable notifications with rabbitmq
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
        },
    )


@pytest.fixture
def mocked_notifications_rpc_client(
    mocker: MockerFixture,
) -> MockerFixture:
    """Mock RabbitMQ RPC calls for notifications templates"""

    # Mock the RPC interface functions
    mocker.patch(
        f"{_service.__name__}.remote_preview_template",
        autospec=True,
    )

    mocker.patch(
        f"{_service.__name__}.remote_search_templates",
        autospec=True,
    )

    return mocker


@pytest.fixture
def create_test_users(
    client: TestClient,
) -> Callable[..., AbstractAsyncContextManager[list[UserInfoDict]]]:
    @asynccontextmanager
    async def _create(count: int = 1, statuses: list | None = None) -> AsyncIterator[list[UserInfoDict]]:
        async with AsyncExitStack() as stack:
            users: list[UserInfoDict] = []

            for i in range(count):
                user_data = {"status": statuses[i]} if statuses and i < len(statuses) else None

                user = await stack.enter_async_context(NewUser(user_data=user_data, app=client.app))
                users.append(user)

            yield users

    return _create
