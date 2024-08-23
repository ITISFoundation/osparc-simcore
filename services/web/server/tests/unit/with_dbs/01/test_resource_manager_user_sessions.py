# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import time
from collections.abc import Callable
from random import randint
from uuid import uuid4

import pytest
import redis.asyncio as aioredis
from aiohttp import web
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.application_setup import is_setup_completed
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.resource_manager.registry import (
    _ALIVE_SUFFIX,
    _RESOURCE_SUFFIX,
    RedisResourceRegistry,
    get_registry,
)
from simcore_service_webserver.resource_manager.settings import get_plugin_settings
from simcore_service_webserver.resource_manager.user_sessions import (
    UserSessionID,
    managed_resource,
)
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed


@pytest.fixture
def mock_env_devel_environment(
    mock_env_devel_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    return mock_env_devel_environment | setenvs_from_dict(
        monkeypatch, {"RESOURCE_MANAGER_RESOURCE_TTL_S": "3"}
    )


@pytest.fixture
def redis_enabled_app(
    redis_client: aioredis.Redis, mocker, mock_env_devel_environment
) -> web.Application:
    # app.cleanup_ctx.append(redis_client) in setup_redis would create a client and connect
    # to a real redis service. Instead, we mock the get_redis_resources_client access
    mocker.patch(
        "simcore_service_webserver.redis.get_redis_resources_client",
        return_value=redis_client,
    )
    mocker.patch(
        "simcore_service_webserver.resource_manager.registry.get_redis_resources_client",
        return_value=redis_client,
    )
    # ------------------

    app = create_safe_application()
    assert setup_settings(app)
    assert setup_resource_manager(app)

    assert is_setup_completed("simcore_service_webserver.redis", app)
    assert get_plugin_settings(app).RESOURCE_MANAGER_RESOURCE_TTL_S == 3
    assert get_registry(app)

    return app


@pytest.fixture
def redis_registry(redis_enabled_app: web.Application) -> RedisResourceRegistry:
    return get_registry(redis_enabled_app)


@pytest.fixture
def create_user_ids():
    def _do(number: int) -> list[int]:
        return list(range(number))

    return _do


@pytest.mark.parametrize(
    "key, hash_key",
    [
        ({"some_key": "some_value"}, "some_key=some_value"),
        (
            {"some_key": "some_value", "another_key": "another_value"},
            "some_key=some_value:another_key=another_value",
        ),
    ],
)
async def test_redis_registry_hashes(redis_enabled_app: web.Application, key, hash_key):
    # pylint: disable=protected-access
    assert RedisResourceRegistry._hash_key(key) == hash_key
    assert (
        RedisResourceRegistry._decode_hash_key(f"{hash_key}:{_RESOURCE_SUFFIX}") == key
    )
    assert RedisResourceRegistry._decode_hash_key(f"{hash_key}:{_ALIVE_SUFFIX}") == key


async def test_redis_registry(redis_registry: RedisResourceRegistry):
    random_value = randint(1, 10)
    key = {f"key_{x}": f"value_{x}" for x in range(random_value)}
    second_key = {f"sec_key_{x}": f"sec_value_{x}" for x in range(random_value)}
    invalid_key = {"invalid_key": "invalid_value"}
    NUM_RESOURCES = 7
    resources = [(f"res_key{x}", f"res_value{x}") for x in range(NUM_RESOURCES)]
    invalid_resource = ("invalid_res_key", "invalid_res_value")

    # create resources
    for res in resources:
        await redis_registry.set_resource(key, res)
        assert len(await redis_registry.get_resources(key)) == resources.index(res) + 1

    # get them
    assert await redis_registry.get_resources(key) == {x[0]: x[1] for x in resources}
    assert not await redis_registry.get_resources(invalid_key)
    # find them
    for res in resources:
        assert await redis_registry.find_resources(key, res[0]) == [res[1]]
        assert not await redis_registry.find_resources(invalid_key, res[0])
        assert not await redis_registry.find_resources(key, invalid_resource[0])
        assert await redis_registry.find_keys(res) == [key]
        assert not await redis_registry.find_keys(invalid_resource)
    # add second key
    for res in resources:
        await redis_registry.set_resource(second_key, res)
        assert (
            len(await redis_registry.get_resources(second_key))
            == resources.index(res) + 1
        )
    # find them
    for res in resources:
        assert await redis_registry.find_resources(key, res[0]) == [res[1]]
        assert not await redis_registry.find_resources(invalid_key, res[0])
        assert not await redis_registry.find_resources(key, invalid_resource[0])
        assert not await redis_registry.find_resources(second_key, invalid_resource[0])
        found_keys = await redis_registry.find_keys(res)
        assert all(x in found_keys for x in [key, second_key])
        assert all(x in [key, second_key] for x in found_keys)
        assert not await redis_registry.find_keys(invalid_resource)

    DEAD_KEY_TIMEOUT = 1
    STILL_ALIVE_KEY_TIMEOUT = DEAD_KEY_TIMEOUT + 1

    # create a key which will be alive when testing
    await redis_registry.set_key_alive(key, STILL_ALIVE_KEY_TIMEOUT)
    assert await redis_registry.is_key_alive(key) is True
    # create soon to be dead key
    await redis_registry.set_key_alive(second_key, DEAD_KEY_TIMEOUT)
    alive_keys, dead_keys = await redis_registry.get_all_resource_keys()
    assert not dead_keys
    assert all(x in alive_keys for x in [key, second_key])
    assert all(x in [key, second_key] for x in alive_keys)

    time.sleep(DEAD_KEY_TIMEOUT)

    assert await redis_registry.is_key_alive(second_key) is False
    alive_keys, dead_keys = await redis_registry.get_all_resource_keys()
    assert alive_keys == [key]
    assert dead_keys == [second_key]

    # clean up
    await redis_registry.remove_key(key)
    assert await redis_registry.is_key_alive(key) is False
    for res in resources:
        assert await redis_registry.find_keys(res) == [second_key]
        await redis_registry.remove_resource(second_key, res[0])
        assert len(await redis_registry.get_resources(second_key)) == len(resources) - (
            resources.index(res) + 1
        )


async def test_redis_registry_key_will_always_expire(
    redis_registry: RedisResourceRegistry,
):
    def get_random_int():
        return randint(1, 10)

    first_key = {f"key_{x}": f"value_{x}" for x in range(get_random_int())}
    second_key = {f"sec_key_{x}": f"sec_value_{x}" for x in range(get_random_int())}

    resources = [(f"res_key{x}", f"res_value{x}") for x in range(get_random_int())]
    for resource in resources:
        await redis_registry.set_resource(first_key, resource)
        await redis_registry.set_resource(second_key, resource)

    await redis_registry.set_key_alive(first_key, 0)
    await redis_registry.set_key_alive(second_key, -3000)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        reraise=True,
    ):

        with attempt:
            print(
                f"checking redis registry for keys alive, [attempt {attempt.retry_state.attempt_number}]..."
            )
            assert await redis_registry.is_key_alive(second_key) is False
            assert await redis_registry.is_key_alive(first_key) is False

    alive_keys, dead_keys = await redis_registry.get_all_resource_keys()
    assert len(alive_keys) == 0
    assert len(dead_keys) == 2


async def test_users_sessions_resources_registry(
    redis_enabled_app: web.Application,
    redis_registry: RedisResourceRegistry,
    create_user_ids: Callable,
):
    # create some user ids and socket ids
    NUM_USER_IDS = 5
    list_user_ids = create_user_ids(NUM_USER_IDS)
    NUM_SOCKET_IDS = 6

    res_key = "some_key"
    res_value = "some_value"

    # add sockets ( <=> connecting user sessions )
    tabs = {}
    for user_id in list_user_ids:
        user = f"user id {user_id}"
        for socket in range(NUM_SOCKET_IDS):
            socket_id = f"{user}_{socket}"
            client_session_id = str(uuid4())
            assert socket_id not in tabs
            tabs[socket_id] = client_session_id

            with managed_resource(user_id, client_session_id, redis_enabled_app) as rt:
                user_session_key = {
                    "user_id": f"{user_id}",
                    "client_session_id": client_session_id,
                }
                assert rt._resource_key() == user_session_key

                # set the socket id and check it is rightfully there
                await rt.set_socket_id(socket_id)
                assert await rt.get_socket_id() == socket_id
                assert await redis_registry.get_resources(user_session_key) == {
                    "socket_id": socket_id
                }
                list_of_sockets_of_user = await rt.find_socket_ids()
                assert socket_id in list_of_sockets_of_user

                # resource key shall be empty
                assert await rt.find(res_key) == []

                # add the resource now
                await rt.add(res_key, res_value)
                assert await redis_registry.get_resources(user_session_key) == {
                    "socket_id": socket_id,
                    res_key: res_value,
                }

                # resource key shall be filled
                assert await rt.find(res_key) == [res_value]
                list_of_same_resource_users: list[
                    UserSessionID
                ] = await rt.find_users_of_resource(
                    redis_enabled_app, res_key, res_value
                )
                assert list_user_ids[: (list_user_ids.index(user_id) + 1)] == sorted(
                    {
                        user_session.user_id
                        for user_session in list_of_same_resource_users
                    }
                )

    # remove sockets (<=> disconnecting user sessions)
    for user_id in list_user_ids:
        user = f"user id {user_id}"
        for socket in range(NUM_SOCKET_IDS):
            socket_id = f"{user}_{socket}"
            client_session_id = tabs[socket_id]

            with managed_resource(user_id, client_session_id, redis_enabled_app) as rt:
                await rt.remove_socket_id()

                num_sockets_for_user = len(await rt.find_socket_ids())
                assert num_sockets_for_user == (NUM_SOCKET_IDS - socket - 1)

                list_of_sockets_of_user = await rt.find_socket_ids()
                assert socket_id not in list_of_sockets_of_user
                assert len(list_of_sockets_of_user) == num_sockets_for_user

                assert await rt.find(res_key) == [res_value]
