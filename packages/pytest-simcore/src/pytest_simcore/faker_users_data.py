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
from pydantic import EmailStr, TypeAdapter

from .helpers.faker_factories import DEFAULT_TEST_PASSWORD, random_user

_MESSAGE = (
    "If set, it overrides the fake value of `{}` fixture."
    " Can be handy when interacting with external/real APIs"
)


_FAKE_USER_EMAIL_OPTION = "--faker-user-email"


def pytest_addoption(parser: pytest.Parser):
    simcore_group = parser.getgroup("simcore")
    simcore_group.addoption(
        "--faker-user-id",
        action="store",
        type=int,
        default=None,
        help=_MESSAGE.format("user_id"),
    )
    simcore_group.addoption(
        _FAKE_USER_EMAIL_OPTION,
        action="store",
        type=str,
        default=None,
        help=_MESSAGE.format("user_email"),
    )
    simcore_group.addoption(
        "--faker-user-api-key",
        action="store",
        type=str,
        default=None,
        help=_MESSAGE.format("user_api_key"),
    )
    simcore_group.addoption(
        "--faker-user-api-secret",
        action="store",
        type=str,
        default=None,
        help=_MESSAGE.format("user_api_secret"),
    )


@pytest.fixture
def user_id(faker: Faker, request: pytest.FixtureRequest) -> UserID:
    return TypeAdapter(UserID).validate_python(
        request.config.getoption("--faker-user-id", default=None) or faker.pyint(),
    )


@pytest.fixture(scope="session")
def is_external_user_email(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption(_FAKE_USER_EMAIL_OPTION, default=None))


@pytest.fixture
def user_email(faker: Faker, request: pytest.FixtureRequest) -> EmailStr:
    return TypeAdapter(EmailStr).validate_python(
        request.config.getoption(_FAKE_USER_EMAIL_OPTION, default=None)
        or faker.email(),
    )


@pytest.fixture
def user_first_name(faker: Faker) -> str:
    return faker.first_name()


@pytest.fixture
def user_last_name(faker: Faker) -> str:
    return faker.last_name()


@pytest.fixture
def user_name(user_email: str) -> IDStr:
    return TypeAdapter(IDStr).validate_python(user_email.split("@")[0])


@pytest.fixture
def user_password(faker: Faker) -> str:
    return faker.password(length=len(DEFAULT_TEST_PASSWORD))


@pytest.fixture
def user_api_key(user_name: str, request: pytest.FixtureRequest) -> str:
    return str(
        request.config.getoption("--faker-user-api-key", default=None)
        or f"api-key-{user_name}"
    )


@pytest.fixture
def user_api_secret(user_password: str, request: pytest.FixtureRequest) -> str:
    return str(
        request.config.getoption("--faker-user-api-secret", default=None)
        or f"api-secret-{user_password}"
    )


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
