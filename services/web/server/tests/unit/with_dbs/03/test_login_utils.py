# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
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
from servicelib.statics_constants import FRONTEND_APPS_AVAILABLE
from simcore_service_webserver._constants import RQ_PRODUCT_KEY
from simcore_service_webserver.email import setup_email
from simcore_service_webserver.login.utils import (
    get_template_path,
    render_and_send_mail,
    themed,
)


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
    app_ = web.Application()
    assert setup_email(app_)
    return app_


def _create_mocked_request(app_: web.Application, product_name: str):
    request = make_mocked_request("GET", "/fake", app=app_)
    request[RQ_PRODUCT_KEY] = product_name
    return request


@pytest.mark.parametrize("product_name", FRONTEND_APPS_AVAILABLE)
async def test_render_and_send_mail_for_registration(
    app: web.Application,
    faker: Faker,
    mocked_send_email: MagicMock,
    product_name: str,
):
    request = _create_mocked_request(app, product_name)
    email = faker.email()  # destination email
    link = faker.url()  # some url link

    await render_and_send_mail(
        request,
        to=email,
        template=await get_template_path(request, "registration_email.jinja2"),
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


@pytest.mark.parametrize("product_name", FRONTEND_APPS_AVAILABLE)
async def test_render_and_send_mail_for_password(
    app: web.Application,
    faker: Faker,
    mocked_send_email: MagicMock,
    product_name: str,
):
    request = _create_mocked_request(app, product_name)
    email = faker.email()  # destination email
    link = faker.url()  # some url link

    await render_and_send_mail(
        request,
        to=email,
        template=await get_template_path(request, "reset_password_email_failed.jinja2"),
        context={
            "host": request.host,
            "reason": faker.text(),
        },
    )

    await render_and_send_mail(
        request,
        to=email,
        template=await get_template_path(request, "reset_password_email.jinja2"),
        context={
            "host": request.host,
            "link": link,
        },
    )


@pytest.mark.parametrize("product_name", FRONTEND_APPS_AVAILABLE)
async def test_render_and_send_mail_to_change_email(
    app: web.Application,
    faker: Faker,
    mocked_send_email: MagicMock,
    product_name: str,
):
    request = _create_mocked_request(app, product_name)
    email = faker.email()  # destination email
    link = faker.url()  # some url link

    await render_and_send_mail(
        request,
        to=email,
        template=await get_template_path(request, "change_email_email.jinja2"),
        context={
            "host": request.host,
            "link": link,
        },
    )


@pytest.mark.parametrize("product_name", FRONTEND_APPS_AVAILABLE)
async def test_render_and_send_mail_for_submission(
    app: web.Application,
    faker: Faker,
    mocked_send_email: MagicMock,
    product_name: str,
):
    request = _create_mocked_request(app, product_name)
    email = faker.email()  # destination email
    data = {"name": faker.first_name(), "surname": faker.last_name()}  # some form

    await render_and_send_mail(
        request,
        to=email,
        template=await get_template_path(request, "service_submission.jinja2"),
        context={
            "user": email,
            "data": json2html.convert(
                json=json.dumps(data), table_attributes='class="pure-table"'
            ),
            "subject": "TEST",
        },
        attachments=[("test_login_utils.py", bytearray(Path(__file__).read_bytes()))],
    )


@pytest.mark.skip(reason="DEV")
def test_render_string_from_tmp_file(
    tmp_path: Path, faker: Faker, app: web.Application
):
    request = make_mocked_request("GET", "/fake", app=app)

    template_path = themed("templates/osparc.io", "registration_email.jinja2")
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
