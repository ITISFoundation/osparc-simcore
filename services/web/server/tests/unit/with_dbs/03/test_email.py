# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from pytest import MockerFixture, MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from pytest_simcore.helpers.utils_login import LoggedUser, UserRole
from simcore_service_webserver._meta import API_VTAG


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


def mock_smtp(mocker: MockerFixture) -> MockerFixture:
    mock = mocker.patch("aiosmtplib.SMTP")
    instance = mock.return_value
    return instance


async def test_email(client: TestClient, faker: Faker, mock_smtp: MockerFixture):

    # TODO: test access by roles
    # TODO: test ping
    # TODO: test send
    async with LoggedUser(client, params={"role": UserRole.ADMIN}) as user:

        assert user
        response = await client.post(
            f"/{API_VTAG}/email:test", data={"to": faker.email()}
        )

        mock_smtp.send_message.assert_called_once_with(
            "from@example.com", ["to@example.com"], "Subject\n\nBody"
        )
        # mock_smtp.assert_called_once_with("localhost")

        # TODO:
        # mock_message.assert_called_once_with()
        # message.__setitem__.assert_any_call("From", "from@example.com")
        ##message.__setitem__.assert_any_call("To", "to@example.com")
        # message.__setitem__.assert_any_call("Subject", "Subject")
        # message.set_content.assert_called_once_with("Body")
        # instance.send_message.assert_called_once_with(message)

        assert response.status == 200
