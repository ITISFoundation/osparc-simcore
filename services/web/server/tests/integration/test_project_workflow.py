"""
    TODO: move to system testing: shall test different workflows on framework studies (=project)
        e.g. run, pull, push ,... pipelines
        This one here is too similar to unit/with_postgres/test_projects.py
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from asyncio import Future, Task, wait_for
from copy import deepcopy
from pathlib import Path
from pprint import pprint
from typing import Dict, List, Optional, Union

import pytest
import sqlalchemy as sa
from aiohttp import web

from models_library.projects import ProjectState
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from pytest_simcore.helpers.utils_projects import delete_all_projects
from servicelib.application import create_safe_application
from simcore_service_webserver import catalog
from simcore_service_webserver.catalog import setup_catalog
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.products import setup_products
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects.projects_fakes import Fake
from simcore_service_webserver.resource_manager import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session

API_VERSION = "v0"

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    "catalog",
    "director",
    "director-v2",
    "postgres",
    "redis",
]

ops_services = ["adminer"]  # + ["adminer"]


@pytest.fixture
def client(
    loop,
    mock_orphaned_services,
    aiohttp_client,
    app_config,  # waits until swarm with *_services are up
):
    assert app_config["rest"]["version"] == API_VERSION

    app_config["main"]["testing"] = True

    app_config["storage"]["enabled"] = False
    app_config["computation"]["enabled"] = False

    pprint(app_config)

    app = create_safe_application(app_config)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_resource_manager(app)
    assert setup_projects(app)
    setup_catalog(app)
    setup_products(app)

    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_config["main"]["port"],
                "host": app_config["main"]["host"],
            },
        )
    )


@pytest.fixture(scope="session")
def fake_template_projects(package_dir: Path) -> Dict:
    projects_file = package_dir / "data" / "fake-template-projects.json"
    assert projects_file.exists()
    with projects_file.open() as fp:
        return json.load(fp)


@pytest.fixture(scope="session")
def fake_template_projects_isan(package_dir: Path) -> Dict:
    projects_file = package_dir / "data" / "fake-template-projects.isan.json"
    assert projects_file.exists()
    with projects_file.open() as fp:
        return json.load(fp)


@pytest.fixture(scope="session")
def fake_template_projects_osparc(package_dir: Path) -> Dict:
    projects_file = package_dir / "data" / "fake-template-projects.osparc.json"
    assert projects_file.exists()
    with projects_file.open() as fp:
        return json.load(fp)


@pytest.fixture
def fake_db():
    Fake.reset()
    yield Fake
    Fake.reset()


@pytest.fixture
def fake_project_data(fake_data_dir: Path) -> Dict:
    with (fake_data_dir / "fake-project.json").open() as fp:
        return json.load(fp)


@pytest.fixture
async def logged_user(client):  # , role: UserRole):
    """adds a user in db and logs in with client

    NOTE: role fixture is defined as a parametrization below
    """
    role = UserRole.USER  # TODO: parameterize roles

    async with LoggedUser(
        client, {"role": role.name}, check_if_succeeds=role != UserRole.ANONYMOUS
    ) as user:
        yield user
        await delete_all_projects(client.app)


@pytest.fixture
async def storage_subsystem_mock(loop, mocker):
    """
    Patches client calls to storage service

    Patched functions are exposed within projects but call storage subsystem
    """
    # requests storage to copy data
    mock = mocker.patch(
        "simcore_service_webserver.projects.projects_api.copy_data_folders_from_project"
    )

    async def _mock_copy_data_from_project(*args):
        return args[2]

    mock.side_effect = _mock_copy_data_from_project

    # requests storage to delete data
    # mock1 = mocker.patch('simcore_service_webserver.projects.projects_handlers.delete_data_folders_of_project', return_value=None)
    mock1 = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.projects_api.delete_data_folders_of_project",
        return_value=Future(),
    )
    mock1.return_value.set_result("")
    return mock, mock1


@pytest.fixture
async def catalog_subsystem_mock(monkeypatch):
    services_in_project = []

    def creator(projects: Optional[Union[List[Dict], Dict]] = None) -> None:
        for proj in projects:
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


# Tests CRUD operations --------------------------------------------
# TODO: merge both unit/with_postgress/test_projects


async def _request_list(client) -> List[Dict]:
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(start=0, count=3))

    projects, _ = await assert_status(resp, web.HTTPOk)

    return projects


async def _request_get(client, pid) -> Dict:
    url = client.app.router["get_project"].url_for(project_id=pid)
    resp = await client.get(url)

    project, _ = await assert_status(resp, web.HTTPOk)

    return project


async def _request_create(client, project):
    url = client.app.router["create_projects"].url_for()
    resp = await client.post(url, json=project)

    new_project, _ = await assert_status(resp, web.HTTPCreated)

    return new_project


async def _request_update(client, project, pid):
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(project_id=pid)
    resp = await client.put(url, json=project)

    updated_project, _ = await assert_status(resp, web.HTTPOk)

    return updated_project


async def _request_delete(client, pid):
    url = client.app.router["delete_project"].url_for(project_id=pid)
    resp = await client.delete(url)

    await assert_status(resp, web.HTTPNoContent)


async def test_workflow(
    client,
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    simcore_services,
    fake_project_data,
    catalog_subsystem_mock,
    logged_user,
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    storage_subsystem_mock,
):
    # empty list
    projects = await _request_list(client)
    assert not projects

    # creation
    await _request_create(client, fake_project_data)
    catalog_subsystem_mock([fake_project_data])
    # list not empty
    projects = await _request_list(client)
    assert len(projects) == 1

    assert not ProjectState(**projects[0].pop("state")).locked.value
    for key in projects[0].keys():
        if key not in (
            "uuid",
            "prjOwner",
            "creationDate",
            "lastChangeDate",
            "accessRights",
        ):
            assert projects[0][key] == fake_project_data[key]
    assert projects[0]["prjOwner"] == logged_user["email"]
    assert projects[0]["accessRights"] == {
        str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
    }

    modified_project = deepcopy(projects[0])
    modified_project["name"] = "some other name"
    modified_project["description"] = "John Raynor killed Kerrigan"
    modified_project["workbench"]["ReNamed"] = modified_project["workbench"].pop(
        list(modified_project["workbench"].keys())[0]
    )
    modified_project["workbench"]["ReNamed"]["position"]["x"] = 0
    # share with some group
    modified_project["accessRights"].update(
        {str(standard_groups[0]["gid"]): {"read": True, "write": True, "delete": False}}
    )
    # modify
    pid = modified_project["uuid"]
    await _request_update(client, modified_project, pid)

    # list not empty
    projects = await _request_list(client)
    assert len(projects) == 1

    for key in projects[0].keys():
        if key not in ("lastChangeDate", "state"):
            assert projects[0][key] == modified_project[key]

    # get
    project = await _request_get(client, pid)
    for key in project.keys():
        if key not in ("lastChangeDate", "state"):
            assert project[key] == modified_project[key]

    # delete
    await _request_delete(client, pid)

    # wait for delete tasks to finish
    tasks = Task.all_tasks()
    for task in tasks:
        # TODO: 'async_generator_asend' has no __name__ attr. Python 3.8 gets coros names
        # Expects "delete_project" coros to have __name__ attrs
        # pylint: disable=protected-access
        if "delete_project" in getattr(task._coro, "__name__", ""):
            await wait_for(task, timeout=60.0)

    # list empty
    projects = await _request_list(client)
    assert not projects


async def test_get_invalid_project(
    client,
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    simcore_services,
    logged_user,
):
    url = client.app.router["get_project"].url_for(project_id="some-fake-id")
    resp = await client.get(url)

    await assert_status(resp, web.HTTPNotFound)


async def test_update_invalid_project(
    client,
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    simcore_services,
    logged_user,
):
    url = client.app.router["replace_project"].url_for(project_id="some-fake-id")
    resp = await client.get(url)

    await assert_status(resp, web.HTTPNotFound)


async def test_delete_invalid_project(
    client,
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    simcore_services,
    logged_user,
):
    url = client.app.router["delete_project"].url_for(project_id="some-fake-id")
    resp = await client.delete(url)

    await assert_status(resp, web.HTTPNotFound)


async def test_list_template_projects(
    client,
    postgres_db: sa.engine.Engine,
    docker_registry: str,
    simcore_services,
    logged_user,
    fake_db,
    fake_template_projects,
    fake_template_projects_isan,
    fake_template_projects_osparc,
    catalog_subsystem_mock,
):
    catalog_subsystem_mock(
        fake_template_projects
        + fake_template_projects_isan
        + fake_template_projects_osparc
    )
    fake_db.load_template_projects()
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(url.with_query(type="template"))

    projects, _ = await assert_status(resp, web.HTTPOk)

    # fake-template-projects.json + fake-template-projects.isan.json + fake-template-projects.osparc.json
    assert len(projects) == (
        len(fake_template_projects)
        + len(fake_template_projects_isan)
        + len(fake_template_projects_osparc)
    )
