# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import pytest
from aiohttp.test_utils import TestClient
from models_library.groups import GroupID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_users import NewUser
from simcore_service_webserver.notifications._controller import _rest


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
        },
    )


@pytest.fixture
def mocked_notifications_rpc_client(
    mocker: MockerFixture,
) -> MockerFixture:
    """Mock RabbitMQ RPC calls for notifications templates"""

    # Mock the RPC interface functions
    mocker.patch(
        f"{_rest.__name__}.remote_preview_template",
        autospec=True,
    )

    mocker.patch(
        f"{_rest.__name__}.remote_search_templates",
        autospec=True,
    )

    return mocker


@pytest.fixture
def create_test_users(
    client: TestClient,
):
    @asynccontextmanager
    async def _create(count: int = 1, statuses: list | None = None) -> AsyncIterator[list[GroupID]]:
        async with AsyncExitStack() as exit_stack:
            gids: list[GroupID] = []

            for i in range(count):
                user_data = {}
                if statuses and i < len(statuses):
                    user_data["status"] = statuses[i]

                user = await exit_stack.enter_async_context(
                    NewUser(user_data=user_data if user_data else None, app=client.app)
                )
                gids.append(int(user["primary_gid"]))

            yield gids

    return _create
