# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import re
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from aiohttp_jinja2 import render_string
from faker import Faker
from json2html import json2html
from pytest_mock import MockerFixture
from simcore_service_webserver._resources import resources
from simcore_service_webserver.email import setup_email
from simcore_service_webserver.login.utils import render_and_send_mail, themed


@pytest.fixture
def mocked_send_email(mocker: MockerFixture) -> MagicMock:
    async def print_mail(app, msg):
        print("EMAIL----------")
        print(msg)
        print("---------------")

    return mocker.patch(
        "simcore_service_webserver.login.utils.send_mail",
        spec=True,
        side_effect=print_mail,
    )


@pytest.fixture
def app() -> web.Application:
    app = web.Application()
    assert setup_email(app)
    return app


@pytest.mark.parametrize(
    "template_path",
    list(resources.get_path("templates").rglob("*.html")),
    ids=lambda p: f"{p.parent}/{p.name}",
)
def test_all_email_templates_include_subject(template_path: Path, app: web.Application):
    assert template_path.exists()
    subject, body = template_path.read_text().split("\n", 1)
    assert (
        re.match(r"[a-zA-Z0-9\-_\s]+", subject) or "{{subject}}" in subject
    ), f"Template {template_path} must start with a subject line, got {subject}"


@pytest.mark.skip(reason="DEV")
def test_render_string_from_tmp_file(
    tmp_path: Path, faker: Faker, app: web.Application
):
    """ """
    request = make_mocked_request("GET", "/fake", app=app)

    template_path = themed("templates/osparc.io", "registration_email.html")
    copy_path = tmp_path / template_path.name
    shutil.copy2(template_path, copy_path)

    context = {"host": request.host, "link": faker.url(), "name": faker.first_name()}

    expected_page = render_string(
        template_name=f"{template_path}",
        request=request,
        context=context,
    )
    got_page = render_string(
        template_name=f"{copy_path}",
        request=request,
        context=context,
    )

    assert expected_page == got_page


async def test_render_and_send_mail(
    app: web.Request, faker: Faker, mocked_send_email: MagicMock
):
    request = make_mocked_request("GET", "/fake", app=app)

    THEME: str = "templates/osparc.io"
    COMMON_THEME: str = "templates/common"

    product = "osparc"
    assert themed(f"templates/{product}", "registration_email.html")

    email = faker.email()  # destination email
    link = faker.url()  # some url link

    await render_and_send_mail(
        request,
        to=email,
        template=themed(THEME, "registration_email.html"),
        context={
            "host": request.host,
            "link": link,
            "name": email.split("@")[0],
        },
    )

    assert mocked_send_email.called
    mimetext = mocked_send_email.call_args[0][1]
    assert mimetext["Subject"]
    assert mimetext["To"] == email

    await render_and_send_mail(
        request,
        to=email,
        template=themed(COMMON_THEME, "reset_password_email_failed.html"),
        context={
            "host": request.host,
            "reason": faker.text(),
        },
    )

    await render_and_send_mail(
        request,
        to=email,
        template=themed(COMMON_THEME, "reset_password_email.html"),
        context={
            "host": request.host,
            "link": link,
        },
    )

    await render_and_send_mail(
        request,
        to=email,
        template=themed(COMMON_THEME, "change_email_email.html"),
        context={
            "host": request.host,
            "link": link,
        },
    )

    data = {"name": faker.first_name(), "surname": faker.last_name()}
    await render_and_send_mail(
        request,
        to=email,
        template=themed(COMMON_THEME, "service_submission.html"),
        context={
            "user": email,
            "data": json2html.convert(
                json=json.dumps(data), table_attributes='class="pure-table"'
            ),
            "subject": "TEST",
        },
        attachments=[("test_login_utils.py", bytearray(Path(__file__).read_bytes()))],
    )
