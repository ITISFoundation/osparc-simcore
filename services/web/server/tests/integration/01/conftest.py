# pylint:disable=unused-argument

import asyncio
from copy import deepcopy
from typing import Callable, Dict, Tuple
from unittest import mock
from uuid import UUID

import aiopg
import aiopg.sa
import pytest
from models_library.projects import ProjectID
from pytest_simcore.helpers.utils_login import AUserDict, log_client_in
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
from simcore_service_webserver.security_roles import UserRole
from yarl import URL

API_VERSION = "v0"
API_PREFIX = f"/{API_VERSION}"
# store only lowercase "v1", "v2", etc...
SUPPORTED_EXPORTER_VERSIONS = {"v1", "v2"}


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


@pytest.fixture
def login_user_and_import_study() -> Callable:
    async def executable(client, export_version) -> Tuple[ProjectID, AUserDict]:
        user = await log_client_in(
            client=client, user_data={"role": UserRole.USER.name}
        )
        export_file_name = export_version.name
        version_from_name = export_file_name.split("#")[0]

        assert_error = (
            f"The '{version_from_name}' version' is not present in the supported versions: "
            f"{SUPPORTED_EXPORTER_VERSIONS}. If it's a new version please remember to add it."
        )
        assert version_from_name in SUPPORTED_EXPORTER_VERSIONS, assert_error

        url_import = client.app.router["import_project"].url_for()
        assert url_import == URL(API_PREFIX + "/projects:import")

        data = {"fileName": open(export_version, mode="rb")}
        async with await client.post(
            url_import, data=data, timeout=10
        ) as import_response:
            assert import_response.status == 200, await import_response.text()
            reply_data = await import_response.json()
            assert reply_data.get("data") is not None

        imported_project_uuid = reply_data["data"]["uuid"]

        return UUID(imported_project_uuid), user

    return executable
