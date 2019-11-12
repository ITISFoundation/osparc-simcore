# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pprint

import pytest
import yaml
from aiohttp import web

from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.activity import setup_activity
from simcore_service_webserver.computation import setup_computation
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users
from utils_assert import assert_status
from utils_login import LoggedUser

API_VERSION = "v0"

core_services = [
    'director',
    'apihub',
    'rabbit',
    'postgres',
    'sidecar',
    'storage'
]

ops_services = [
    'minio'
#    'adminer',
#    'portainer'
]

@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, app_config, here):
    port = app_config["main"]["port"] = aiohttp_unused_port()
    host = app_config['main']['host'] = '127.0.0.1'

    assert app_config["rest"]["version"] == API_VERSION
    assert API_VERSION in app_config["rest"]["location"]

    app_config['storage']['enabled'] = False
    app_config["db"]["init_tables"] = True # inits postgres_service

    final_config_path = here / "config.app.yaml"
    with final_config_path.open('wt') as f:
        yaml.dump(app_config, f, default_flow_style=False)

    # fake config
    app = create_safe_application()
    app[APP_CONFIG_KEY] = app_config

    pprint(app_config)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_projects(app)
    setup_computation(app)
    setup_activity(app)

    yield loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': host
    }))

    # cleanup
    final_config_path.unlink()

@pytest.fixture
async def logged_user(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds = user_role!=UserRole.ANONYMOUS
    ) as user:
        yield user


@pytest.mark.parametrize("user_role,expected_response", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_with_prometheus(client, postgres_session, logged_user, expected_response):
    url = client.app.router["get_status"].url_for()
    resp = await client.get(url)
    data, error = await assert_status(resp, expected_response)
