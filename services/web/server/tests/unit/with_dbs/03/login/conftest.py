# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import uuid
from collections.abc import AsyncIterable, Iterator
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserStatus
from faker import Faker
from models_library.basic_types import IDStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from simcore_postgres_database.models.products import ProductLoginSettingsDict, products
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.login._confirmation_repository import (
    ConfirmationRepository,
)
from simcore_service_webserver.login._confirmation_service import ConfirmationService
from simcore_service_webserver.login.settings import LoginOptions, get_plugin_options
from simcore_service_webserver.notifications import notifications_service


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, faker: Faker):
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
def fake_weak_password(faker: Faker) -> str:
    return faker.password(length=8, special_chars=True, digits=True, upper_case=True, lower_case=True)


@pytest.fixture
def confirmation_repository(client: TestClient) -> ConfirmationRepository:
    """Modern confirmation repository instance"""
    assert client.app
    # Get the async engine from the application
    engine = get_asyncpg_engine(client.app)
    return ConfirmationRepository(engine)


@pytest.fixture
def confirmation_service(
    confirmation_repository: ConfirmationRepository, login_options: LoginOptions
) -> ConfirmationService:
    """Confirmation service instance"""
    return ConfirmationService(confirmation_repository, login_options)


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
def mocked_notifications_service_send_message_from_template(
    mocker: MockerFixture,
) -> AsyncMock:
    return mocker.patch(
        f"{notifications_service.__name__}.send_message_from_template",
        autospec=True,
        return_value=(uuid.uuid4(), "send_message_from_template"),
    )


@pytest.fixture
def cleanup_db_tables(postgres_db: sa.engine.Engine) -> Iterator[None]:
    yield
    with postgres_db.connect() as conn:
        conn.execute(wallets.delete())
        conn.execute(users.delete())


@pytest.fixture
def postgres_db_with_2fa_enabled_for_osparc(postgres_db: sa.engine.Engine) -> sa.engine.Engine:
    """Adds a fake twilio_messaging_sid and enables 2FA for the 'osparc' product (pre-initialized).

    NOTE: LOGIN_2FA_REQUIRED requires LOGIN_REGISTRATION_INVITATION_REQUIRED=1 (see
    LoginSettings._login_2fa_needs_confirmed_email), so callers must also set that env var.
    """
    stmt = (
        products.update()
        .values(
            twilio_messaging_sid="x" * 34,
            login_settings=ProductLoginSettingsDict(LOGIN_2FA_REQUIRED=True),
        )
        .where(products.c.name == "osparc")
    )
    with postgres_db.connect() as conn:
        conn.execute(stmt)
    return postgres_db
