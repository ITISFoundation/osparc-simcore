# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from collections.abc import AsyncIterable, Iterator

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserStatus
from faker import Faker
from models_library.basic_types import IDStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.login._login_repository_legacy import (
    AsyncpgStorage,
    get_plugin_storage,
)
from simcore_service_webserver.login.settings import LoginOptions, get_plugin_options


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, faker: Faker
):
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_GROUPS": "1",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_PRODUCTS": "1",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "1",  # for login notifications
            "WEBSERVER_STUDIES_DISPATCHER": "null",
            "WEBSERVER_TAGS": "1",
            "WEBSERVER_WALLETS": "1",
            "WEBSERVER_TRACING": "null",
        },
    )

    monkeypatch.delenv("WEBSERVER_LOGIN", raising=False)
    app_environment.pop("WEBSERVER_LOGIN", None)

    envs_login = setenvs_from_dict(
        monkeypatch,
        {
            "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED": "1",
            "LOGIN_REGISTRATION_INVITATION_REQUIRED": "1",
            "LOGIN_2FA_CODE_EXPIRATION_SEC": "60",
        },
    )

    monkeypatch.delenv("LOGIN_TWILIO", raising=False)
    app_environment.pop("LOGIN_TWILIO", None)

    envs_twilio = setenvs_from_dict(
        monkeypatch,
        {
            "TWILIO_ACCOUNT_SID": "fake-twilio-account",
            "TWILIO_AUTH_TOKEN": "fake-twilio-token",
            "TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT": json.dumps(["41"]),
        },
    )

    return {**app_environment, **envs_plugins, **envs_login, **envs_twilio}


@pytest.fixture
def user_phone_number(faker: Faker) -> str:
    return faker.phone_number()


@pytest.fixture
def fake_weak_password(faker: Faker) -> str:
    return faker.password(
        length=8, special_chars=True, digits=True, upper_case=True, lower_case=True
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
    user_name: IDStr,
    user_email: str,
    user_password: str,
    user_phone_number: str,
    client: TestClient,
) -> AsyncIterable[UserInfoDict]:
    async with NewUser(
        user_data={
            "name": user_name,
            "email": user_email,
            "password": user_password,
            "phone": user_phone_number,
            "status": UserStatus.ACTIVE,
        },
        app=client.app,
    ) as user:
        yield user


@pytest.fixture
async def unconfirmed_user(
    user_name: str,
    user_email: str,
    user_password: str,
    user_phone_number: str,
    client: TestClient,
) -> AsyncIterable[UserInfoDict]:
    async with NewUser(
        user_data={
            "name": user_name,
            "email": user_email,
            "password": user_password,
            "phone": user_phone_number,
            "status": UserStatus.CONFIRMATION_PENDING,
        },
        app=client.app,
    ) as user:
        yield user


@pytest.fixture
def mocked_email_core_remove_comments(mocker: MockerFixture):
    def _do_not_remove_comments(html_string):
        return html_string

    mocker.patch(
        "simcore_service_webserver.email._core._remove_comments",
        autospec=True,
        side_effect=_do_not_remove_comments,
    )


@pytest.fixture
def cleanup_db_tables(postgres_db: sa.engine.Engine) -> Iterator[None]:
    yield
    with postgres_db.connect() as conn:
        conn.execute(wallets.delete())
        conn.execute(users.delete())
