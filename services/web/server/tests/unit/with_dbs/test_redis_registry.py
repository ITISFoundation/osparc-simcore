# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import time
from random import randint
from typing import Dict, List
from uuid import uuid4

import pytest

from simcore_service_webserver.resource_manager.config import (
    APP_CLIENT_REDIS_CLIENT_KEY,
    APP_CLIENT_SOCKET_REGISTRY_KEY,
    APP_CONFIG_KEY,
    CONFIG_SECTION_NAME,
)
from simcore_service_webserver.resource_manager.registry import (
    ALIVE_SUFFIX,
    RESOURCE_SUFFIX,
    RedisResourceRegistry,
)
from simcore_service_webserver.resource_manager.websocket_manager import (
    managed_resource,
)


@pytest.fixture
def redis_enabled_app(redis_client) -> Dict:
    app = {
        APP_CLIENT_REDIS_CLIENT_KEY: redis_client,
        APP_CLIENT_SOCKET_REGISTRY_KEY: None,
        APP_CONFIG_KEY: {CONFIG_SECTION_NAME: {"resource_deletion_timeout_seconds": 3}},
    }
    yield app


@pytest.fixture
def redis_registry(redis_enabled_app) -> RedisResourceRegistry:
    registry = RedisResourceRegistry(redis_enabled_app)
    redis_enabled_app[APP_CLIENT_SOCKET_REGISTRY_KEY] = registry
    yield registry


@pytest.fixture
def user_ids():
    def create_user_id(number: int) -> List[str]:
        return [i for i in range(number)]

    return create_user_id


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
async def test_redis_registry_hashes(loop, redis_enabled_app, key, hash_key):
    # pylint: disable=protected-access
    assert RedisResourceRegistry._hash_key(key) == hash_key
    assert (
        RedisResourceRegistry._decode_hash_key(f"{hash_key}:{RESOURCE_SUFFIX}") == key
    )
    assert RedisResourceRegistry._decode_hash_key(f"{hash_key}:{ALIVE_SUFFIX}") == key


async def test_redis_registry(loop, redis_registry):
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

    # create alive key
    await redis_registry.set_key_alive(key, True)
    assert await redis_registry.is_key_alive(key) == True
    # create soon to be dead key
    TIMEOUT = 3
    await redis_registry.set_key_alive(second_key, False, TIMEOUT)
    alive_keys, dead_keys = await redis_registry.get_all_resource_keys()
    assert not dead_keys
    assert all(x in alive_keys for x in [key, second_key])
    assert all(x in [key, second_key] for x in alive_keys)
    time.sleep(TIMEOUT)
    assert await redis_registry.is_key_alive(second_key) == False
    alive_keys, dead_keys = await redis_registry.get_all_resource_keys()
    assert alive_keys == [key]
    assert dead_keys == [second_key]

    # clean up
    await redis_registry.remove_key(key)
    assert await redis_registry.is_key_alive(key) == False
    for res in resources:
        assert await redis_registry.find_keys(res) == [second_key]
        await redis_registry.remove_resource(second_key, res[0])
        assert len(await redis_registry.get_resources(second_key)) == len(resources) - (
            resources.index(res) + 1
        )


async def test_websocket_manager(loop, redis_enabled_app, redis_registry, user_ids):

    # create some user ids and socket ids
    NUM_USER_IDS = 5
    list_user_ids = user_ids(NUM_USER_IDS)
    NUM_SOCKET_IDS = 6

    res_key = "some_key"
    res_value = "some_value"

    # add sockets
    tabs = {}
    for user_id in list_user_ids:
        user = f"user id {user_id}"
        for socket in range(NUM_SOCKET_IDS):
            socket_id = f"{user}_{socket}"
            client_session_id = str(uuid4())
            assert socket_id not in tabs
            tabs[socket_id] = client_session_id
            with managed_resource(user_id, client_session_id, redis_enabled_app) as rt:
                # pylint: disable=protected-access
                resource_key = {"user_id": f"{user_id}", "client_session_id": client_session_id}
                assert rt._resource_key() == resource_key

                # set the socket id and check it is rightfully there
                await rt.set_socket_id(socket_id)
                assert await rt.get_socket_id() == socket_id
                assert await redis_registry.get_resources(resource_key) == {
                    "socket_id": socket_id
                }
                list_of_sockets_of_user = await rt.find_socket_ids()
                assert socket_id in list_of_sockets_of_user
                # resource key shall be empty
                assert await rt.find(res_key) == []
                # add the resource now
                await rt.add(res_key, res_value)
                assert await redis_registry.get_resources(resource_key) == {
                    "socket_id": socket_id,
                    res_key: res_value,
                }
                # resource key shall be filled
                assert await rt.find(res_key) == [res_value]
                list_of_same_resource_users = await rt.find_users_of_resource(
                    res_key, res_value
                )
                assert list_user_ids[: (list_user_ids.index(user_id) + 1)] == sorted(
                    list_of_same_resource_users
                )

    # remove sockets
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
