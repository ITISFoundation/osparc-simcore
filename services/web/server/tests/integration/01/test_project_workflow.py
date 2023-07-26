# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


"""
    TODO: move to system testing: shall test different workflows on framework studies (=project)
        e.g. run, pull, push ,... pipelines
        This one here is too similar to unit/with_postgres/test_projects.py
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from copy import deepcopy
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest
import redis.asyncio as aioredis
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects_state import ProjectState
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.long_running_tasks.client import LRTask
from servicelib.aiohttp.long_running_tasks.server import TaskProgress
from servicelib.aiohttp.long_running_tasks.server import (
    setup as setup_long_running_tasks,
)
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.catalog.plugin import setup_catalog
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.director_v2.plugin import setup_director_v2
from simcore_service_webserver.garbage_collector.plugin import setup_garbage_collector
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.products.plugin import setup_products
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session

API_VERSION = "v0"

# Selection of core and tool services started in this swarm fixture (integration)
pytest_simcore_core_services_selection = [
    "catalog",
    "director",
    "migration",
    "postgres",
    "redis",
]

pytest_simcore_ops_services_selection = ["adminer"]  # + ["adminer"]


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    mock_orphaned_services: mock.Mock,
    aiohttp_client: Callable[..., Awaitable[TestClient]],
    app_config: dict[str, Any],  # waits until swarm with *_services are up
    monkeypatch_setenv_from_app_config: Callable,
    redis_client: aioredis.Redis,
    rabbit_service: RabbitSettings,
    simcore_services_ready: None,
) -> Iterator[TestClient]:
    assert app_config["rest"]["version"] == API_VERSION

    app_config["main"]["testing"] = True

    app_config["storage"]["enabled"] = False
    app_config["computation"]["enabled"] = False

    monkeypatch_setenv_from_app_config(app_config)
    app = create_safe_application(app_config)

    assert setup_settings(app)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_long_running_tasks(app, router_prefix="/tasks")
    setup_rest(app)
    setup_login(app)
    setup_resource_manager(app)
    setup_garbage_collector(app)
    assert setup_projects(app)
    setup_catalog(app)
    setup_products(app)
    setup_director_v2(app)

    return event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_config["main"]["port"],
                "host": app_config["main"]["host"],
            },
        )
    )


@pytest.fixture
async def storage_subsystem_mock(mocker: MockerFixture):
    """
    Patches client calls to storage service

    Patched functions are exposed within projects but call storage subsystem
    """
    # requests storage to copy data

    async def _mock_copy_data_from_project(app, src_prj, dst_prj, nodes_map, user_id):
        print(
            f"MOCK copying data project {src_prj['uuid']} -> {dst_prj['uuid']} "
            f"with {len(nodes_map)} s3 objects by user={user_id}"
        )

        yield LRTask(TaskProgress(message="pytest mocked fct, started"))

        async def _mock_result():
            return None

        yield LRTask(
            TaskProgress(message="pytest mocked fct, finished", percent=1.0),
            _result=_mock_result(),
        )

    mock = mocker.patch(
        "simcore_service_webserver.projects._crud_create_utils.copy_data_folders_from_project",
        autospec=True,
        side_effect=_mock_copy_data_from_project,
    )

    # requests storage to delete data
    mock1 = mocker.patch(
        "simcore_service_webserver.projects._crud_delete_utils.delete_data_folders_of_project",
        return_value="",
    )
    return mock, mock1


@pytest.fixture
def catalog_subsystem_mock(
    mocker: MockerFixture,
) -> Iterator[Callable[[list[ProjectDict]], None]]:
    """
    Patches some API calls in the catalog plugin
    """
    services_in_project = []

    def _creator(projects: list[ProjectDict]) -> None:
        for proj in projects or []:
            services_in_project.extend(
                [
                    {"key": s["key"], "version": s["version"]}
                    for _, s in proj["workbench"].items()
                ]
            )

    async def _mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    for namespace in (
        "simcore_service_webserver.projects._crud_read_utils.get_services_for_user_in_product",
        "simcore_service_webserver.projects._handlers_crud.get_services_for_user_in_product",
    ):
        mock = mocker.patch(
            namespace,
            autospec=True,
        )

        mock.side_effect = _mocked_get_services_for_user

    yield _creator

    services_in_project.clear()


# Tests CRUD operations --------------------------------------------
# TODO: merge both unit/with_postgress/test_projects


async def _request_list(client) -> list[dict]:
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(offset=0, limit=3))

    projects, _ = await assert_status(resp, web.HTTPOk)

    return projects


async def _request_get(client, pid) -> dict:
    url = client.app.router["get_project"].url_for(project_id=pid)
    resp = await client.get(url)

    project, _ = await assert_status(resp, web.HTTPOk)

    return project


async def _request_replace(client, project, pid):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=pid)
    resp = await client.put(url, json=project)

    updated_project, _ = await assert_status(resp, web.HTTPOk)

    return updated_project


async def _request_delete(client, pid):
    url = client.app.router["delete_project"].url_for(project_id=pid)
    resp = await client.delete(url)

    await assert_status(resp, web.HTTPNoContent)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_workflow(
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    fake_project: ProjectDict,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    client,
    logged_user,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    storage_subsystem_mock,
    director_v2_service_mock,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    # empty list
    projects = await _request_list(client)
    assert not projects

    # creation
    for invalid_key in ["uuid", "creationDate", "lastChangeDate"]:
        fake_project.pop(invalid_key)
    await request_create_project(
        client,
        web.HTTPAccepted,
        web.HTTPCreated,
        logged_user,
        primary_group,
        project=fake_project,
    )
    catalog_subsystem_mock([fake_project])
    # list not empty
    projects = await _request_list(client)
    assert len(projects) == 1

    assert not ProjectState(**projects[0].pop("state")).locked.value
    for key in projects[0]:
        if key not in (
            "uuid",
            "prjOwner",
            "creationDate",
            "lastChangeDate",
            "accessRights",
        ):
            assert projects[0][key] == fake_project[key]
    assert projects[0]["prjOwner"] == logged_user["email"]
    assert projects[0]["accessRights"] == {
        str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
    }

    modified_project = deepcopy(projects[0])
    modified_project["name"] = "some other name"
    modified_project["description"] = "John Raynor killed Kerrigan"

    new_node_id = str(uuid4())
    modified_project["workbench"][new_node_id] = modified_project["workbench"].pop(
        next(iter(modified_project["workbench"].keys()))
    )
    modified_project["workbench"][new_node_id]["position"]["x"] = 0
    # share with some group
    modified_project["accessRights"].update(
        {str(standard_groups[0]["gid"]): {"read": True, "write": True, "delete": False}}
    )
    # modify
    pid = modified_project["uuid"]
    await _request_replace(client, modified_project, pid)

    # list not empty
    projects = await _request_list(client)
    assert len(projects) == 1

    for key in projects[0]:
        if key not in ("lastChangeDate", "state"):
            assert projects[0][key] == modified_project[key]

    # get
    project = await _request_get(client, pid)
    for key in project:
        if key not in ("lastChangeDate", "state"):
            assert project[key] == modified_project[key]

    # delete
    await _request_delete(client, pid)

    # wait for delete tasks to finish
    tasks = asyncio.all_tasks()
    for task in tasks:
        # TODO: 'async_generator_asend' has no __name__ attr. Python 3.8 gets coros names
        # Expects "delete_project" coros to have __name__ attrs
        # pylint: disable=protected-access
        if "delete_project" in getattr(task.get_coro(), "__name__", ""):
            await asyncio.wait_for(task, timeout=60.0)

    # list empty
    projects = await _request_list(client)
    assert not projects


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_invalid_project(
    client,
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    logged_user,
    faker: Faker,
):
    url = client.app.router["get_project"].url_for(project_id=faker.uuid4())
    resp = await client.get(url)

    await assert_status(resp, web.HTTPNotFound)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_update_invalid_project(
    client,
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    logged_user,
    faker: Faker,
):
    url = client.app.router["replace_project"].url_for(project_id=faker.uuid4())
    resp = await client.get(url)

    await assert_status(resp, web.HTTPNotFound)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_delete_invalid_project(
    client,
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    logged_user,
    faker: Faker,
):
    url = client.app.router["delete_project"].url_for(project_id=faker.uuid4())
    resp = await client.delete(url)

    await assert_status(resp, web.HTTPNotFound)
