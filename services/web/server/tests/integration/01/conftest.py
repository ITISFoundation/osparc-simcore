# pylint:disable=unused-argument

import asyncio
from copy import deepcopy
from typing import Callable, Dict
from unittest import mock

import aiopg
import aiopg.sa
import pytest
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application import (
    setup_director,
    setup_director_v2,
    setup_exporter,
    setup_login,
    setup_products,
    setup_projects,
    setup_resource_manager,
    setup_rest,
    setup_security,
    setup_session,
    setup_socketio,
    setup_storage,
    setup_users,
)
from simcore_service_webserver.catalog import setup_catalog
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.scicrunch.submodule_setup import (
    setup_scicrunch_submodule,
)
from utils import API_VERSION


@pytest.fixture
def client(
    loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: Dict,
    postgres_with_template_db: aiopg.sa.engine.Engine,
    mock_orphaned_services: mock.Mock,
):

    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VERSION
    assert cfg["rest"]["enabled"]
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True

    # fake config
    app = create_safe_application(cfg)

    # activates only security+restAPI sub-modules
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_director(app)
    setup_director_v2(app)
    setup_exporter(app)
    setup_storage(app)
    setup_products(app)
    setup_catalog(app)
    setup_scicrunch_submodule(app)
    assert setup_resource_manager(app)

    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )
