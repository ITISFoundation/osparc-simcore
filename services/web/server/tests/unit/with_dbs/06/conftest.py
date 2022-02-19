# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy
from typing import Callable, Dict, List, Optional, Union

import pytest
from aioresponses import aioresponses
from pytest_simcore.helpers.utils_projects import NewProject, delete_all_projects
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver import catalog
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.director.plugin import setup_director
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.products import setup_products
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.resource_manager.module_setup import (
    setup_resource_manager,
)
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.module_setup import setup_socketio
from simcore_service_webserver.tags import setup_tags

API_VERSION = "v0"
RESOURCE_NAME = "projects"
API_PREFIX = "/" + API_VERSION


DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS: int = 3
DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS: int = 3


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    app_cfg,
    postgres_db,
    mocked_director_v2_api,
    mock_orphaned_services,
    redis_client,  # this ensure redis is properly cleaned
    monkeypatch_setenv_from_app_config: Callable,
):
    # config app
    cfg = deepcopy(app_cfg)
    port = cfg["main"]["port"]
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True
    cfg["resource_manager"][
        "garbage_collection_interval_seconds"
    ] = DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS  # increase speed of garbage collection
    cfg["resource_manager"][
        "resource_deletion_timeout_seconds"
    ] = DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS  # reduce deletion delay

    monkeypatch_setenv_from_app_config(cfg)

    app = create_safe_application(cfg)

    assert setup_settings(app)

    # setup app
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)  # needed for login_utils fixtures
    setup_resource_manager(app)
    setup_socketio(app)
    setup_director(app)
    setup_director_v2(app)
    setup_tags(app)
    assert setup_projects(app)
    setup_products(app)

    # server and client
    yield loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": port, "host": "localhost"})
    )

    # teardown here ...


@pytest.fixture
async def user_project(client, fake_project, logged_user):
    async with NewProject(
        fake_project, client.app, user_id=logged_user["id"]
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def shared_project(client, fake_project, logged_user, all_group):
    fake_project.update(
        {
            "accessRights": {
                f"{all_group['gid']}": {"read": True, "write": False, "delete": False}
            },
        },
    )
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def template_project(
    client, fake_project, logged_user, all_group: Dict[str, str]
):
    project_data = deepcopy(fake_project)
    project_data["name"] = "Fake template"
    project_data["uuid"] = "d4d0eca3-d210-4db6-84f9-63670b07176b"
    project_data["accessRights"] = {
        str(all_group["gid"]): {"read": True, "write": False, "delete": False}
    }

    async with NewProject(
        project_data, client.app, user_id=None, clear_all=True
    ) as template_project:
        print("-----> added template project", template_project["name"])
        yield template_project
        print("<----- removed template project", template_project["name"])


@pytest.fixture
def fake_services():
    def create_fakes(number_services: int) -> List[Dict]:
        fake_services = [{"service_uuid": f"{i}_uuid"} for i in range(number_services)]
        return fake_services

    yield create_fakes


@pytest.fixture
async def project_db_cleaner(client):
    yield
    await delete_all_projects(client.app)


@pytest.fixture
async def catalog_subsystem_mock(
    monkeypatch,
) -> Callable[[Optional[Union[List[Dict], Dict]]], None]:
    services_in_project = []

    def creator(projects: Optional[Union[List[Dict], Dict]] = None) -> None:
        for proj in projects or []:
            services_in_project.extend(
                [
                    {"key": s["key"], "version": s["version"]}
                    for _, s in proj["workbench"].items()
                ]
            )

    async def mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    monkeypatch.setattr(
        catalog, "get_services_for_user_in_product", mocked_get_services_for_user
    )

    return creator


@pytest.fixture(autouse=True)
async def director_v2_automock(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    yield director_v2_service_mock
