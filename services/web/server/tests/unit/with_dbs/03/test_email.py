# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from pydantic import ValidationError
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.helpers.utils_login import LoggedUser, UserRole
from settings_library.email import EmailProtocol, SMTPSettings
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.email_handlers import TestFailed, TestPassed


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: MonkeyPatch):
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_CLUSTERS": "null",
            "WEBSERVER_COMPUTATION": "null",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_DIRECTOR": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_GROUPS": "1",
            "WEBSERVER_META_MODELING": "null",
            "WEBSERVER_PRODUCTS": "1",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "1",  # for login notifications
            "WEBSERVER_STUDIES_ACCESS_ENABLED": "0",
            "WEBSERVER_TAGS": "1",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_USERS": "1",
            "WEBSERVER_VERSION_CONTROL": "0",
        },
    )

    monkeypatch.delenv("WEBSERVER_EMAIL", raising=False)
    app_environment.pop("WEBSERVER_EMAIL", None)

    envs_email = setenvs_from_dict(
        monkeypatch,
        {
            "SMTP_HOST": "mail.server.com",
            "SMTP_PORT": "25",
            "SMTP_USERNAME": "user",
            "SMTP_PASSWORD": "secret",
        },
    )

    return {**app_environment, **envs_plugins, **envs_email}


@pytest.fixture
def mock_smtp(mocker: MockerFixture, app_environment: EnvVarsDict) -> MagicMock:

    settings = SMTPSettings.create_from_envs()

    mock = mocker.patch("aiosmtplib.SMTP")
    instance = mock.return_value.__aenter__.return_value
    instance.hostname = settings.SMTP_HOST
    instance.port = settings.SMTP_PORT
    instance.timeout = 100
    instance.use_tls = settings.SMTP_PROTOCOL == EmailProtocol.TLS

    return mock


async def test_email_handlers(client: TestClient, faker: Faker, mock_smtp: MagicMock):

    async with LoggedUser(client, params={"role": UserRole.ADMIN.value}) as user:

        assert user
        destination_email = faker.email()

        response = await client.post(
            f"/{API_VTAG}/email:test", json={"to": destination_email}
        )

        data, error = await assert_status(response, expected_cls=web.HTTPOk)
        print(data)

        assert data
        assert error is None

        with pytest.raises(ValidationError):
            failed = TestFailed.parse_obj(data)

        passed = TestPassed.parse_obj(data)
        print(passed.json(indent=1))
