# pylint:disable=redefined-outer-name

import pytest
from faker import Faker
from models_library.api_schemas_webserver.socketio import SocketIORoom
from models_library.users import GroupID, UserID


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return UserID(faker.pyint())


@pytest.fixture
def group_id(faker: Faker) -> GroupID:
    return GroupID(faker.pyint())


@pytest.fixture
def socket_id(faker: Faker) -> str:
    return faker.pystr()


def test_socketio_room(user_id: UserID, group_id: GroupID, socket_id: str):
    assert SocketIORoom.from_user_id(user_id) == f"user:{user_id}"
    assert SocketIORoom.from_group_id(group_id) == f"{group_id}"
    assert SocketIORoom.from_socket_id(socket_id) == socket_id
