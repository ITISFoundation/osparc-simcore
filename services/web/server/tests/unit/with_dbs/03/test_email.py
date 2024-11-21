# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import functools
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from faker import Faker
from pydantic import ValidationError
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict, UserRole
from servicelib.aiohttp import status
from settings_library.email import EmailProtocol, SMTPSettings
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver._resources import webserver_resources
from simcore_service_webserver.email._core import _remove_comments, _render_template
from simcore_service_webserver.email._handlers import EmailTestFailed, EmailTestPassed
from simcore_service_webserver.email.plugin import setup_email
from simcore_service_webserver.login._registration_api import _json_encoder_and_dumps
from simcore_service_webserver.login._registration_handlers import _get_ipinfo


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_GROUPS": "1",
            "WEBSERVER_META_MODELING": "0",
            "WEBSERVER_PRODUCTS": "1",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "1",  # for login notifications
            "WEBSERVER_STUDIES_DISPATCHER": "null",
            "WEBSERVER_TAGS": "1",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_VERSION_CONTROL": "0",
            "WEBSERVER_WALLETS": "0",
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
async def mocked_aiosmtplib(mocker: MockerFixture) -> MagicMock:
    mocked_lib = mocker.patch("aiosmtplib.SMTP", autospec=True)
    settings = SMTPSettings.create_from_envs()
    mocked_lib.return_value.__aenter__.return_value.hostname = settings.SMTP_HOST
    mocked_lib.return_value.__aenter__.return_value.port = settings.SMTP_PORT
    mocked_lib.return_value.__aenter__.return_value.timeout = 100
    mocked_lib.return_value.__aenter__.return_value.use_tls = (
        settings.SMTP_PROTOCOL == EmailProtocol.TLS
    )
    return mocked_lib


@pytest.fixture
async def mocked_send_email(
    mocked_aiosmtplib: MagicMock, mocker: MockerFixture, app_environment: EnvVarsDict
) -> MagicMock:
    # Overrides services/web/server/tests/unit/with_dbs/conftest.py::mocked_send_email
    return mocked_aiosmtplib.return_value


@pytest.mark.parametrize(
    "user_role,expected_response_cls",
    [
        (UserRole.ADMIN, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
    ],
)
async def test_email_handlers(
    client: TestClient,
    faker: Faker,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected_response_cls: type[web.Response],
    mocked_aiosmtplib: MagicMock,
    mocked_send_email: MagicMock,
):
    assert logged_user["role"] == user_role.name
    destination_email = faker.email()

    response = await client.post(
        f"/{API_VTAG}/email:test", json={"to": destination_email}
    )

    data, error = await assert_status(
        response, expected_status_code=expected_response_cls
    )

    if error:
        assert not mocked_send_email.called

    if data:
        print(mocked_send_email.mock_calls)
        assert mocked_send_email.send_message.called

        print(json.dumps(data, indent=1))
        assert data
        assert error is None

        with pytest.raises(ValidationError):
            EmailTestFailed.model_validate(data)

        passed = EmailTestPassed.model_validate(data)
        print(passed.model_dump_json(indent=1))


class IndexParser(HTMLParser):
    def __init__(self):
        self.tags = []
        self.has_comments = False
        super().__init__()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_endtag(self, tag):
        self.tags.append(tag)

    def handle_comment(self, data):
        self.has_comments = True

    def error(self, message):
        # this is an override for py3.9
        assert self
        assert not message


@pytest.mark.parametrize(
    "template_path",
    list(webserver_resources.get_path("templates").rglob("*.jinja2")),
    ids=lambda p: p.name,
)
def test_render_templates(template_path: Path, faker: Faker):
    app = web.Application()
    setup_email(app)

    request = make_mocked_request(
        "GET",
        "/fake",
        headers={
            "x-real-ip": faker.ipv4(),
            "x-forwarded-for": faker.ipv4(),
            "peername": faker.ipv4(),
        },
        app=app,
    )

    fake_request_form = {
        "name": faker.name(),
        "user": {
            "name": faker.name(),
            "address": faker.address(),
            "email": faker.email(),
        },
        "job": {
            "title": faker.job(),
            "company": {"name": faker.company(), "address": faker.address()},
        },
    }

    subject, html_body = _render_template(
        request,
        template_path,
        context={
            "host": request.host,
            "support_email": faker.email(),
            "name": "this is user.first_name",
            "code": "123",
            "reason": "no reason",
            "link": faker.url(),
            "product": SimpleNamespace(name="foobar", display_name="Foo Bar"),
            "retention_days": 30,
            "dumps": functools.partial(_json_encoder_and_dumps, indent=1),
            "request_form": fake_request_form,
            "ipinfo": _get_ipinfo(request),
        },
    )

    assert subject
    assert html_body

    # parses html (will fail if detects some )
    parser = IndexParser()
    parser.feed(html_body)

    assert not parser.has_comments

    # '==2' means it was started and closed
    counter = Counter(parser.tags)
    assert counter["body"] == 2
    assert counter["html"] == 2
    assert counter["head"] == 2


def test_remove_comments():
    uncommented_html = _remove_comments(
        """
    <!--
          hi this is
           a
           multiline comment

           ^&#@!%***
    -->
    <b>and this is not</b>     <!-- inline comment -->
    """
    ).strip()

    assert uncommented_html == "<b>and this is not</b>"
