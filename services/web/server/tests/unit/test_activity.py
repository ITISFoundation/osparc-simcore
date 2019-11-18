# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import importlib
from pathlib import Path

import yaml

import pytest
from aiohttp import web
from servicelib.application import create_safe_application
from simcore_service_webserver.activity import handlers, setup_activity
from simcore_service_webserver.application import create_application
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from utils_assert import assert_status


@pytest.fixture
def mocked_login_required(mocker):
    patched = mocker.patch('simcore_service_webserver.login.decorators.login_required', lambda f: f)
    importlib.reload(handlers)
    return patched
    

@pytest.fixture
def mocked_prometeheus_failure(mocker):
    mocker.patch('simcore_service_webserver.activity.handlers.get_cpu_usage').return_value = None


@pytest.fixture
def app_config(fake_data_dir: Path, osparc_simcore_root_dir: Path):
    with open(fake_data_dir/"test_activity_config.yml") as fh:
        content = fh.read()
        config = content.replace("${OSPARC_SIMCORE_REPO_ROOTDIR}", str(osparc_simcore_root_dir))

    return yaml.load(config)


@pytest.fixture
def client(loop, aiohttp_client, app_config):
    # app = create_application(app_config)
    app = create_safe_application(app_config)

    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_activity(app)

    cli = loop.run_until_complete(aiohttp_client(app))
    return cli


async def test_get_status(mocked_login_required, client, mocked_prometeheus_failure):
    resp = await client.get('/v0/activity/status')
    data, _ = await assert_status(resp, web.HTTPOk)
