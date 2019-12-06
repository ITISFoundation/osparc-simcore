# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from typing import Dict, List
from uuid import uuid4

import pytest
from simcore_service_webserver.resource_manager.config import \
    APP_CLIENT_REDIS_CLIENT_KEY
from simcore_service_webserver.resource_manager.registry import \
    RedisResourceRegistry


@pytest.fixture
def fake_app() -> Dict:
    app = {
        APP_CLIENT_REDIS_CLIENT_KEY: None
    }
    yield app

@pytest.fixture
def user_ids():
    def create_user_id(number: int) -> List[str]:
        return [f"user id {i}" for i in range(number)]
    return create_user_id

async def test_websocket_registry(loop, fake_app, redis_client, user_ids):
    fake_app[APP_CLIENT_REDIS_CLIENT_KEY] = redis_client
    registry = RedisResourceRegistry(fake_app)

    # create some user ids and socket ids
    NUM_USER_IDS = 5
    list_user_ids = user_ids(NUM_USER_IDS)
    NUM_SOCKET_IDS = 6

    # add sockets
    for user in list_user_ids:
        for socket in range(NUM_SOCKET_IDS):
            socket_id = f"{user}_{socket}"
            tab_id = str(uuid4())
            num_sockets_for_user = await registry.add_socket(user, tab_id, socket_id)
            assert num_sockets_for_user == (socket + 1)

            list_of_sockets_of_user = await registry.find_sockets(user)
            assert socket_id in list_of_sockets_of_user
            assert len(list_of_sockets_of_user) == num_sockets_for_user

            socket_user_owner = await registry.find_owner(socket_id)
            assert socket_user_owner == user

    # remove sockets
    for user in list_user_ids:
        for socket in range(NUM_SOCKET_IDS):
            socket_id = f"{user}_{socket}"
            num_sockets_for_user = await registry.remove_socket(socket_id)
            assert num_sockets_for_user == (NUM_SOCKET_IDS - socket - 1)

            list_of_sockets_of_user = await registry.find_sockets(user)
            assert socket_id not in list_of_sockets_of_user
            assert len(list_of_sockets_of_user) == num_sockets_for_user

            socket_user_owner = await registry.find_owner(socket_id)
            assert not socket_user_owner
