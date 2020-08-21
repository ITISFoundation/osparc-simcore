# TODO: tests for garbage collector
# - a User with more then 2 projects
# - a user without projects
# - a user with just 1 project
#
#  The user can be:
# - connected via browser (websocket connection is up)
# - disconnected (no websocket connection)
import pytest
from copy import deepcopy

from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, create_user, log_client_in
from pytest_simcore.helpers.utils_projects import NewProject, delete_all_projects


DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS: int = 3
DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS: int = 3



@pytest.fixture(scope="function")
def app_cfg(default_app_cfg, aiohttp_unused_port):
    """ OVERRIDES services/web/server/tests/unit/with_dbs/conftest.py:app_cfg fixture
        to create a webserver with customized config
    """
    cfg = deepcopy(default_app_cfg)

    # fills ports on the fly
    cfg["main"]["port"] = aiohttp_unused_port()
    cfg["storage"]["port"] = aiohttp_unused_port()

    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True
    cfg["diagnostics"]["enabled"] = False
    cfg["tags"]["enabled"] = False

    cfg["resource_manager"]["enabled"] = True
    cfg["resource_manager"][
        "garbage_collection_interval_seconds"
    ] = DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS  # increase speed of garbage collection
    cfg["resource_manager"][
        "resource_deletion_timeout_seconds"
    ] = DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS  # reduce deletion delay


    import logging
    log_level = getattr(logging, cfg["main"]["log_level"])
    logging.root.setLevel(log_level)
    # this fixture can be safely modified during test since it is renovated on every call
    return cfg

from aiohttp import web



async def test_webserver_config(client, api_version_prefix):
    resp = await client.get(f"/{api_version_prefix}/config")

    data, error = await assert_status(resp, web.HTTPOk)

    assert data
    assert not error
