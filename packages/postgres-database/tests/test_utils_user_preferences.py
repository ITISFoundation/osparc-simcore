# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from aiopg.sa.connection import SAConnection
from faker import Faker
from pytest_simcore.helpers.rawdata_fakers import random_user
from simcore_postgres_database.models.users import UserRole, users
from simcore_postgres_database.utils_user_preferences import UserPreferencesRepo


@pytest.fixture
async def user(connection: SAConnection, faker: Faker) -> dict[str, Any]:
    data = random_user(role=faker.random_element(elements=UserRole))
    user_id = await connection.scalar(
        users.insert().values(**data).returning(users.c.id)
    )
    assert user_id
    data["id"] = user_id
    return data


@pytest.fixture
def preference_one() -> str:
    return "pref_one"


@pytest.fixture
def preference_two() -> str:
    return "pref_two"


async def _assert_save_get_preference(
    connection: SAConnection, *, user_id: int, preference_name: str, payload: bytes
) -> None:
    await UserPreferencesRepo().save_preference(
        connection,
        user_id=user_id,
        preference_name=preference_name,
        payload=payload,
    )
    get_res_2: bytes | None = await UserPreferencesRepo().get_preference_payload(
        connection, user_id=user_id, preference_name=preference_name
    )
    assert get_res_2 is not None
    assert get_res_2 == payload


def _get_random_payload(faker: Faker) -> bytes:
    return faker.pystr(max_chars=10000).encode()


async def test_user_preference_repo_workflow(
    connection: SAConnection, user: dict[str, Any], preference_one: str, faker: Faker
):
    # preference is not saved
    not_found: bytes | None = await UserPreferencesRepo().get_preference_payload(
        connection, user_id=user["id"], preference_name=preference_one
    )
    assert not_found is None

    payload_1 = _get_random_payload(faker)
    payload_2 = _get_random_payload(faker)
    assert payload_1 != payload_2

    # store the preference for the first time
    await _assert_save_get_preference(
        connection,
        user_id=user["id"],
        preference_name=preference_one,
        payload=payload_1,
    )

    # updating the preference still works
    await _assert_save_get_preference(
        connection,
        user_id=user["id"],
        preference_name=preference_one,
        payload=payload_2,
    )


# TEST same preference name with different users do not get overwritten
