# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
"""
    Fixtures to produce fake data for a user:
        - it is self-consistent
        - granular customization by overriding fixtures
"""

from typing import Any

import pytest
from faker import Faker
from models_library.basic_types import IDStr
from models_library.users import UserID
from pydantic import EmailStr, parse_obj_as

from .helpers.rawdata_fakers import DEFAULT_TEST_PASSWORD, random_user


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return parse_obj_as(UserID, faker.pyint())


@pytest.fixture
def user_email(faker: Faker) -> EmailStr:
    return parse_obj_as(EmailStr, faker.email())


@pytest.fixture
def user_first_name(faker: Faker) -> str:
    return faker.first_name()


@pytest.fixture
def user_last_name(faker: Faker) -> str:
    return faker.last_name()


@pytest.fixture
def user_name(user_email: str) -> IDStr:
    return parse_obj_as(IDStr, user_email.split("@")[0])


@pytest.fixture
def user_password(faker: Faker) -> str:
    return faker.password(length=len(DEFAULT_TEST_PASSWORD))


@pytest.fixture
def user(
    faker: Faker,
    user_id: UserID,
    user_email: EmailStr,
    user_first_name: str,
    user_last_name: str,
    user_name: IDStr,
    user_password: str,
) -> dict[str, Any]:
    return random_user(
        id=user_id,
        email=user_email,
        name=user_name,
        first_name=user_first_name,
        last_name=user_last_name,
        password=user_password,
        fake=faker,
    )
