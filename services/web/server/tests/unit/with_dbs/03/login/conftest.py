# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
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
    assert client.app
    db: AsyncpgStorage = get_plugin_storage(client.app)
    assert db
    return db


@pytest.fixture
def cfg(client: TestClient) -> LoginOptions:
    assert client.app
    cfg = get_plugin_options(client.app)
    assert cfg
    return cfg
