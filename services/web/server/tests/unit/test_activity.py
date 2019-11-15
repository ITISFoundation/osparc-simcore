# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path

import pytest
import yaml
from aiohttp import web
from servicelib.application import create_safe_application
from simcore_service_webserver.activity import setup_activity
from simcore_service_webserver.application import create_application
from simcore_service_webserver.login.decorators import login_required
from simcore_service_webserver.rest import setup_rest
from utils_assert import assert_status


@pytest.fixture
def mocked_loged_in_user(mocker):
    # https://pypi.org/project/pytest-mock/
    #
    get_status.get_cpu_usage
    get_memory_usage
    get_celery_reserved
    get_container_metric_for_labels


@pytest.fixture
def app_config(fake_data_dir: Path, osparc_simcore_root_dir: Path):
    with open(fake_data_dir/"test_activity_config.yml") as fh:
        content = fh.read()
        content.replace("${OSPARC_SIMCORE_REPO_ROOTDIR}", str(osparc_simcore_root_dir))

    cfg = yaml.load(content)
    return cfg




@pytest.fixture
def client(loop, aiohttp_client, app_config):
    #app = create_application(app_config)

    ## OR

    app = create_safe_application(app_config)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_activity(app)

    cli = loop.run_until_complete( aiohttp_client(app) )
    return cli


async def test_get_status(client, mocker):
    login_required_mock = mocker.mock(login_required)
    login_required_mock.return_value = lambda h:h

    mock_get_cpu_usage = mocker.patch(get_cpu_usage)
    fut = Future()
    fut.set_result()
    mock_get_cpu_usage.execute.return_value = fut



    resp = await client.get('/v0/activity/status')
    data, _ = await assert_status(resp, web.HTTOK)

    assert data['stats']['cpuUsage'] == 5
