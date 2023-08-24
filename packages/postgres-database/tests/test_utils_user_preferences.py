# pylint: disable=redefined-outer-name

import pytest
from aiopg.sa.connection import SAConnection
from faker import Faker
from pytest_simcore.helpers.rawdata_fakers import random_user
from simcore_postgres_database.models.users import UserRole, users
from simcore_postgres_database.utils_user_preferences import UserPreferencesRepo


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


async def _assert_preference_not_saved(
    connection: SAConnection, *, user_id: int, preference_name: str
) -> None:
    not_found: bytes | None = await UserPreferencesRepo().get_preference_payload(
        connection, user_id=user_id, preference_name=preference_name
    )
    assert not_found is None


def _get_random_payload(faker: Faker) -> bytes:
    return faker.pystr(max_chars=10000).encode()


async def _get_user_id(connection: SAConnection, faker: Faker) -> int:
    data = random_user(role=faker.random_element(elements=UserRole))
    user_id = await connection.scalar(
        users.insert().values(**data).returning(users.c.id)
    )
    assert user_id
    return user_id


async def test_user_preference_repo_workflow(
    connection: SAConnection, preference_one: str, faker: Faker
):
    user_id = await _get_user_id(connection, faker)
    # preference is not saved
    await _assert_preference_not_saved(
        connection, user_id=user_id, preference_name=preference_one
    )

    payload_1 = _get_random_payload(faker)
    payload_2 = _get_random_payload(faker)
    assert payload_1 != payload_2

    # store the preference for the first time
    await _assert_save_get_preference(
        connection,
        user_id=user_id,
        preference_name=preference_one,
        payload=payload_1,
    )

    # updating the preference still works
    await _assert_save_get_preference(
        connection,
        user_id=user_id,
        preference_name=preference_one,
        payload=payload_2,
    )


async def test_same_preference_name_different_users(
    connection: SAConnection, preference_one: str, faker: Faker
):
    user_id_1 = await _get_user_id(connection, faker)
    user_id_2 = await _get_user_id(connection, faker)

    payload_1 = _get_random_payload(faker)
    payload_2 = _get_random_payload(faker)
    assert payload_1 != payload_2

    # save preference for first user
    await _assert_preference_not_saved(
        connection, user_id=user_id_1, preference_name=preference_one
    )
    await _assert_save_get_preference(
        connection,
        user_id=user_id_1,
        preference_name=preference_one,
        payload=payload_1,
    )

    # save preference for second user
    await _assert_preference_not_saved(
        connection, user_id=user_id_2, preference_name=preference_one
    )
    await _assert_save_get_preference(
        connection,
        user_id=user_id_2,
        preference_name=preference_one,
        payload=payload_2,
    )


async def test_different_preferences_same_user(
    connection: SAConnection, preference_one: str, preference_two: str, faker: Faker
):
    user_id = await _get_user_id(connection, faker)

    payload_1 = _get_random_payload(faker)
    payload_2 = _get_random_payload(faker)
    assert payload_1 != payload_2

    # save first preference
    await _assert_preference_not_saved(
        connection, user_id=user_id, preference_name=preference_one
    )
    await _assert_save_get_preference(
        connection,
        user_id=user_id,
        preference_name=preference_one,
        payload=payload_1,
    )

    # save second preference
    await _assert_preference_not_saved(
        connection, user_id=user_id, preference_name=preference_two
    )
    await _assert_save_get_preference(
        connection,
        user_id=user_id,
        preference_name=preference_two,
        payload=payload_2,
    )
