# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest_simcore.helpers.utils_login import NewUser, UserInfoDict
from simcore_service_webserver.login.settings import LoginOptions, get_plugin_options
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage


@pytest.fixture
def fake_user_email(faker: Faker) -> str:
    return faker.email()


@pytest.fixture
def fake_user_name(fake_user_email: str) -> str:
    return fake_user_email.split("@")[0]


@pytest.fixture
def fake_user_phone_number(faker: Faker) -> str:
    return faker.phone_number()


@pytest.fixture
def fake_user_password(faker: Faker) -> str:
    return faker.password(
        length=12, special_chars=True, digits=True, upper_case=True, lower_case=True
    )


@pytest.fixture
def db(client: TestClient) -> AsyncpgStorage:
    """login database repository instance"""
    assert client.app
    db: AsyncpgStorage = get_plugin_storage(client.app)
    assert db
    return db


@pytest.fixture
def login_options(client: TestClient) -> LoginOptions:
    """app's login options"""
    assert client.app
    cfg: LoginOptions = get_plugin_options(client.app)
    assert cfg
    return cfg


@pytest.fixture
async def registered_user(
    fake_user_name: str,
    fake_user_email: str,
    fake_user_password: str,
    fake_user_phone_number: str,
    client: TestClient,
) -> UserInfoDict:
    async with NewUser(
        params={
            "name": fake_user_name,
            "email": fake_user_email,
            "password": fake_user_password,
            "phone": fake_user_phone_number,
            # active user
        },
        app=client.app,
    ) as user:
        yield user
