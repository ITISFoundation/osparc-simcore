# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
import shutil
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from aiohttp_jinja2 import render_string
from faker import Faker
from simcore_service_webserver._resources import webserver_resources
from simcore_service_webserver.email.plugin import setup_email
from simcore_service_webserver.login.utils_email import themed


@pytest.fixture
def app() -> web.Application:
    app = web.Application()
    assert setup_email(app)
    return app


@pytest.mark.parametrize(
    "template_path",
    list(webserver_resources.get_path("templates").rglob("*.jinja2")),
    ids=lambda p: p.name,
)
def test_all_email_templates_include_subject(template_path: Path, app: web.Application):
    assert template_path.exists()
    subject, content = template_path.read_text().split("\n", 1)

    assert re.match(
        r"[\{\}a-zA-Z0-9\-_\s]+", subject.strip("🐼")
    ), f"Template {template_path} must start with a subject line, got {subject}"

    assert content


@pytest.mark.skip(reason="DEV")
def test_render_string_from_tmp_file(
    tmp_path: Path, faker: Faker, app: web.Application
):
    """ """
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
