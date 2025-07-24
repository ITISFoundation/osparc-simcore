# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import contextlib
import logging
import re
from collections.abc import AsyncIterable, Awaitable, Callable
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Any, NamedTuple
from unittest import mock
from uuid import UUID, uuid4

import aiopg
import aiopg.sa
import pytest
import redis.asyncio as aioredis
import socketio
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from models_library.groups import EVERYONE_GROUP_ID, StandardGroupCreate
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from pytest_mock import MockerFixture
from pytest_simcore.helpers import webserver_projects
from pytest_simcore.helpers.webserver_login import log_client_in
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.models import projects, users
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.director_v2.plugin import setup_director_v2
from simcore_service_webserver.garbage_collector import _core as gc_core
from simcore_service_webserver.garbage_collector._tasks_core import _GC_TASK_NAME
from simcore_service_webserver.garbage_collector.plugin import setup_garbage_collector
from simcore_service_webserver.groups._groups_service import create_standard_group
from simcore_service_webserver.groups.api import add_user_in_group
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.projects import _projects_repository
from simcore_service_webserver.projects._crud_api_delete import get_scheduled_tasks
from simcore_service_webserver.projects._groups_repository import (
    update_or_insert_project_group,
)
from simcore_service_webserver.projects.exceptions import ProjectNotFoundError
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.plugin import setup_projects
from simcore_service_webserver.resource_manager.plugin import setup_resource_manager
from simcore_service_webserver.resource_manager.registry import (
    UserSessionDict,
    get_registry,
)
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session
from simcore_service_webserver.socketio.plugin import setup_socketio
from simcore_service_webserver.users.plugin import setup_users
from sqlalchemy import func, select
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

log = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "migration",  # NOTE: rebuild!
    "postgres",
    "rabbit",
    "redis",
    "storage",  # NOTE: rebuild!
]
pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
    "redis-commander",
]


API_VERSION = "v0"
GARBAGE_COLLECTOR_INTERVAL = 1
SERVICE_DELETION_DELAY = 1
# ensure enough time has passed and GC was triggered
WAIT_FOR_COMPLETE_GC_CYCLE = GARBAGE_COLLECTOR_INTERVAL + SERVICE_DELETION_DELAY + 2


@pytest.fixture(autouse=True)
def _drop_and_recreate_postgres(database_from_template_before_each_function):
    return


@pytest.fixture(autouse=True)
async def _delete_all_redis_keys(redis_settings: RedisSettings):
    client = aioredis.from_url(
        redis_settings.build_redis_dsn(RedisDatabase.RESOURCES),
        encoding="utf-8",
        decode_responses=True,
    )
    await client.flushall()
    await client.aclose(close_connection_pool=True)


@pytest.fixture
async def director_v2_service_mock(
    mocker: MockerFixture,
) -> AsyncIterable[aioresponses]:
    """uses aioresponses to mock all calls of an aiohttpclient
    WARNING: any request done through the client will go through aioresponses. It is
    unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
    Other than that it seems to behave nicely
    """
    PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]
    get_computation_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations/.*$"
    )
    delete_computation_pattern = get_computation_pattern

    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.list_dynamic_services",
        autospec=True,
        return_value={},
    )

    # NOTE: GitHK I have to copy paste that fixture for some unclear reason for now.
    # I think this is due to some conflict between these non-pytest-simcore fixtures and the loop fixture being defined at different locations?? not sure..
    # anyway I think this should disappear once the garbage collector moves to its own micro-service
    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        mock.get(
            get_computation_pattern,
            status=status.HTTP_202_ACCEPTED,
            payload={"state": str(RunningState.NOT_STARTED.value)},
            repeat=True,
        )
        mock.delete(delete_computation_pattern, status=204, repeat=True)
        yield mock


@pytest.fixture
async def client(
    aiohttp_client: Callable[..., Awaitable[TestClient]],
    app_config: dict[str, Any],
    postgres_with_template_db: sa.engine.Engine,
    mock_orphaned_services: mock.Mock,
    monkeypatch_setenv_from_app_config: Callable,
    redis_client: aioredis.Redis,
    rabbit_service: RabbitSettings,
    simcore_services_ready: None,
    director_v2_service_mock: aioresponses,
) -> TestClient:
    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VERSION
    assert cfg["rest"]["enabled"]

    cfg["projects"]["enabled"] = True
    cfg["resource_manager"].update(
        {
            "garbage_collection_interval_seconds": GARBAGE_COLLECTOR_INTERVAL,  # increase speed of garbage collection
            "resource_deletion_timeout_seconds": SERVICE_DELETION_DELAY,  # reduce deletion delay
        }
    )

    monkeypatch_setenv_from_app_config(cfg)
    app = create_safe_application(cfg)

    # activates only security+restAPI sub-modules
    assert setup_settings(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_director_v2(app)

    assert setup_resource_manager(app)

    setup_garbage_collector(app)

    return await aiohttp_client(
        app,
        server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
    )


@pytest.fixture
def disable_garbage_collector_task(mocker: MockerFixture) -> mock.MagicMock:
    """patch the setup of the garbage collector so we can call it manually"""

    def _fake_factory():
        async def _cleanup_ctx_fun(app: web.Application):
            # startup
            await asyncio.sleep(0.1)
            yield
            # teardown
            await asyncio.sleep(0.1)

        return _cleanup_ctx_fun

    return mocker.patch(
        "simcore_service_webserver.garbage_collector.plugin._tasks_core.create_background_task_for_garbage_collection",
        side_effect=_fake_factory,
    )


async def login_user(client: TestClient, *, exit_stack: contextlib.AsyncExitStack):
    """returns a logged in regular user"""
    return await log_client_in(
        client=client, user_data={"role": UserRole.USER.name}, exit_stack=exit_stack
    )


async def login_guest_user(
    client: TestClient, *, exit_stack: contextlib.AsyncExitStack
):
    """returns a logged in Guest user"""
    return await log_client_in(
        client=client, user_data={"role": UserRole.GUEST.name}, exit_stack=exit_stack
    )


async def _setup_project_cleanup(
    client: TestClient,
    project: dict[str, Any],
    exit_stack: contextlib.AsyncExitStack,
) -> None:
    """Helper function to setup project cleanup after test completion"""

    async def _delete_project(project_uuid):
        assert client.app
        with contextlib.suppress(ProjectNotFoundError):
            # Sometimes the test deletes the project
            await _projects_repository.delete_project(
                client.app, project_uuid=project_uuid
            )

    exit_stack.push_async_callback(_delete_project, ProjectID(project["uuid"]))


async def create_standard_project(
    client: TestClient,
    user: UserInfoDict,
    product_name: str,
    tests_data_dir: Path,
    exit_stack: contextlib.AsyncExitStack,
    access_rights: dict[str, Any] | None = None,
):
    """returns a project for the given user"""
    project_data = webserver_projects.empty_project_data()
    if access_rights is not None:
        project_data["accessRights"] = access_rights

    assert client.app
    project = await webserver_projects.create_project(
        client.app,
        project_data,
        user["id"],
        product_name=product_name,
        default_project_json=tests_data_dir / "fake-template-projects.isan.2dplot.json",
    )

    if access_rights:
        for group_id, permissions in access_rights.items():
            await update_or_insert_project_group(
                client.app,
                project_id=project["uuid"],
                group_id=int(group_id),
                read=permissions["read"],
                write=permissions["write"],
                delete=permissions["delete"],
            )

    await _setup_project_cleanup(client, project, exit_stack)
    return project


async def create_template_project(
    client: TestClient,
    user: UserInfoDict,
    product_name: str,
    project_data: ProjectDict,
    exit_stack: contextlib.AsyncExitStack,
    access_rights=None,
):
    """returns a tempalte shared with all"""
    assert client.app

    # the information comes from a file, randomize it
    project_data["name"] = f"Fake template {uuid4()}"
    project_data["uuid"] = f"{uuid4()}"
    project_data["accessRights"] = {
        str(EVERYONE_GROUP_ID): {"read": True, "write": False, "delete": False}
    }
    if access_rights is not None:
        project_data["accessRights"].update(access_rights)

    project = await webserver_projects.create_project(
        client.app,
        project_data,
        user["id"],
        product_name=product_name,
        default_project_json=None,
    )

    await _setup_project_cleanup(client, project, exit_stack)
    return project


async def get_group(client: TestClient, user: UserInfoDict):
    """Creates a group for a given user"""
    assert client.app

    group, _ = await create_standard_group(
        app=client.app,
        user_id=user["id"],
        create=StandardGroupCreate.model_validate(
            {
                "name": f"name-{uuid4()}",
                "description": f"desc-{uuid4()}",
                "thumbnail": None,
            }
        ),
    )
    return group.model_dump(mode="json")


async def invite_user_to_group(client: TestClient, owner, invitee, group):
    """Invite a user to a group on which the owner has writes over"""
    assert client.app

    await add_user_in_group(
        client.app,
        owner["id"],
        group["gid"],
        new_by_user_id=invitee["id"],
    )


async def change_user_role(
    aiopg_engine: aiopg.sa.Engine, user: UserInfoDict, role: UserRole
) -> None:
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            users.update().where(users.c.id == int(user["id"])).values(role=role.value)
        )


class SioConnectionData(NamedTuple):
    sio: socketio.AsyncClient
    resource_key: UserSessionDict


async def connect_to_socketio(
    client: TestClient,
    user,
    socketio_client_factory: Callable[..., Awaitable[socketio.AsyncClient]],
) -> SioConnectionData:
    """Connect a user to a socket.io"""
    assert client.app
    socket_registry = get_registry(client.app)
    cur_client_session_id = f"{uuid4()}"
    sio = await socketio_client_factory(cur_client_session_id, client)
    resource_key: UserSessionDict = {
        "user_id": str(user["id"]),
        "client_session_id": cur_client_session_id,
    }
    sid = sio.get_sid()
    assert sid
    assert await socket_registry.find_keys(("socket_id", sid)) == [resource_key]
    assert sio.get_sid() in await socket_registry.find_resources(
        resource_key, "socket_id"
    )
    assert len(await socket_registry.find_resources(resource_key, "socket_id")) == 1
    return SioConnectionData(sio, resource_key)


async def disconnect_user_from_socketio(
    client: TestClient, sio_connection_data: SioConnectionData
) -> None:
    """disconnect a previously connected socket.io connection"""
    sio, resource_key = sio_connection_data
    sid = sio.get_sid()

    assert client.app
    socket_registry = get_registry(client.app)
    await sio.disconnect()
    assert not sio.sid

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        reraise=True,
    ):
        with attempt:
            assert not await socket_registry.find_keys(("socket_id", sio.get_sid()))
            assert sid not in await socket_registry.find_resources(
                resource_key, "socket_id"
            )
            assert not await socket_registry.find_resources(resource_key, "socket_id")


async def assert_users_count(
    aiopg_engine: aiopg.sa.Engine, expected_users: int
) -> None:
    async with aiopg_engine.acquire() as conn:
        users_count = await conn.scalar(select(func.count()).select_from(users))
        assert users_count == expected_users


async def assert_projects_count(
    aiopg_engine: aiopg.sa.Engine, expected_projects: int
) -> None:
    async with aiopg_engine.acquire() as conn:
        projects_count = await conn.scalar(select(func.count()).select_from(projects))
        assert projects_count == expected_projects


def assert_dicts_match_by_common_keys(first_dict, second_dict) -> None:
    common_keys = set(first_dict.keys()) & set(second_dict.keys())
    for key in common_keys:
        assert first_dict[key] == second_dict[key], key


async def fetch_user_from_db(
    aiopg_engine: aiopg.sa.Engine, user: UserInfoDict
) -> UserInfoDict | None:
    """returns a user from the db"""
    async with aiopg_engine.acquire() as conn:
        user_result = await conn.execute(users.select().where(users.c.id == user["id"]))
        result = await user_result.first()
        if result is None:
            return None
        return UserInfoDict(**dict(result))


async def fetch_project_from_db(
    aiopg_engine: aiopg.sa.Engine, user_project: dict
) -> dict[str, Any]:
    async with aiopg_engine.acquire() as conn:
        project_result = await conn.execute(
            projects.select().where(projects.c.uuid == user_project["uuid"])
        )
        result = await project_result.first()
        assert result
        return dict(result)


async def assert_user_in_db(
    aiopg_engine: aiopg.sa.Engine, logged_user: UserInfoDict
) -> None:
    user = await fetch_user_from_db(aiopg_engine, logged_user)
    assert user
    user_as_dict = dict(user)

    # some values need to be transformed
    user_as_dict["role"] = user_as_dict["role"]  # type: ignore
    user_as_dict["status"] = user_as_dict["status"].value  # type: ignore

    assert_dicts_match_by_common_keys(user_as_dict, logged_user)


async def assert_user_not_in_db(
    aiopg_engine: aiopg.sa.Engine, user: UserInfoDict
) -> None:
    user_db = await fetch_user_from_db(aiopg_engine, user)
    assert user_db is None


def _enum_to_value(d):
    return {k: (v.value if isinstance(v, Enum) else v) for k, v in d.items()}


async def assert_project_in_db(
    aiopg_engine: aiopg.sa.Engine, user_project: dict
) -> None:
    project = await fetch_project_from_db(aiopg_engine, user_project)
    assert project
    project_as_dict = _enum_to_value(dict(project))

    assert_dicts_match_by_common_keys(project_as_dict, user_project)


async def assert_user_is_owner_of_project(
    aiopg_engine: aiopg.sa.Engine, owner_user: UserInfoDict, owner_project: dict
) -> None:
    user = await fetch_user_from_db(aiopg_engine, owner_user)
    assert user

    project = await fetch_project_from_db(aiopg_engine, owner_project)
    assert project

    assert user["id"] == project["prj_owner"]


async def assert_one_owner_for_project(
    aiopg_engine: aiopg.sa.Engine, project: dict, possible_owners: list[UserInfoDict]
) -> None:
    q_owners = [
        await fetch_user_from_db(aiopg_engine, owner) for owner in possible_owners
    ]
    assert all(q_owners)

    q_project = await fetch_project_from_db(aiopg_engine, project)
    assert q_project

    assert q_project["prj_owner"] in {user["id"] for user in q_owners if user}


async def test_t1_while_guest_is_connected_no_resources_are_removed(
    disable_garbage_collector_task: None,
    client: TestClient,
    create_socketio_connection: Callable,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """while a GUEST user is connected GC will not remove none of its projects nor the user itself"""
    assert client.app
    logged_guest_user = await login_guest_user(client, exit_stack=exit_stack)
    empty_guest_user_project = await create_standard_project(
        client,
        logged_guest_user,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
    )
    await assert_users_count(aiopg_engine, 1)
    await assert_projects_count(aiopg_engine, 1)

    await connect_to_socketio(client, logged_guest_user, create_socketio_connection)
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(app=client.app)

    await assert_user_in_db(aiopg_engine, logged_guest_user)
    await assert_project_in_db(aiopg_engine, empty_guest_user_project)


@pytest.mark.flaky(max_runs=3)
async def test_t2_cleanup_resources_after_browser_is_closed(
    disable_garbage_collector_task: None,
    client: TestClient,
    create_socketio_connection: Callable,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """After a GUEST users with one opened project closes browser tab regularly (GC cleans everything)"""
    assert client.app
    logged_guest_user = await login_guest_user(client, exit_stack=exit_stack)
    empty_guest_user_project = await create_standard_project(
        client,
        logged_guest_user,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
    )
    await assert_users_count(aiopg_engine, 1)
    await assert_projects_count(aiopg_engine, 1)

    sio_connection_data = await connect_to_socketio(
        client, logged_guest_user, create_socketio_connection
    )
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(app=client.app)

    # check user and project are still in the DB
    await assert_user_in_db(aiopg_engine, logged_guest_user)
    await assert_project_in_db(aiopg_engine, empty_guest_user_project)

    await disconnect_user_from_socketio(client, sio_connection_data)
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(app=client.app)

    # ensures all project delete tasks are
    delete_tasks = get_scheduled_tasks(
        project_uuid=UUID(empty_guest_user_project["uuid"]),
        user_id=logged_guest_user["id"],
    )
    assert not delete_tasks or all(t.done() for t in delete_tasks)

    # check user and project are no longer in the DB
    async with aiopg_engine.acquire() as conn:
        user_result = await conn.execute(users.select())
        user = await user_result.first()
        project_result = await conn.execute(projects.select())
        project = await project_result.first()

        assert project is None
        assert user is None


async def test_t3_gc_will_not_intervene_for_regular_users_and_their_resources(
    client: TestClient,
    create_socketio_connection: Callable,
    aiopg_engine: aiopg.sa.engine.Engine,
    fake_project: dict,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """after a USER disconnects the GC will remove none of its projects or templates nor the user itself"""
    number_of_projects = 5
    number_of_templates = 5
    logged_user = await login_user(client, exit_stack=exit_stack)
    user_projects = [
        await create_standard_project(
            client, logged_user, osparc_product_name, tests_data_dir, exit_stack
        )
        for _ in range(number_of_projects)
    ]
    user_template_projects = [
        await create_template_project(
            client,
            logged_user,
            osparc_product_name,
            fake_project,
            exit_stack=exit_stack,
        )
        for _ in range(number_of_templates)
    ]

    async def assert_projects_and_users_are_present() -> None:
        # check user and projects and templates are still in the DB
        await assert_user_in_db(aiopg_engine, logged_user)
        for project in user_projects:
            await assert_project_in_db(aiopg_engine, project)
        for template in user_template_projects:
            await assert_project_in_db(aiopg_engine, template)

    await assert_users_count(aiopg_engine, 1)
    expected_count = number_of_projects + number_of_templates
    await assert_projects_count(aiopg_engine, expected_count)

    # connect the user and wait for gc
    sio_connection_data = await connect_to_socketio(
        client, logged_user, create_socketio_connection
    )
    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    await assert_projects_and_users_are_present()

    await disconnect_user_from_socketio(client, sio_connection_data)
    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    await assert_projects_and_users_are_present()


async def test_t4_project_shared_with_group_transferred_to_user_in_group_on_owner_removal(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """
    USER "u1" creates a GROUP "g1" and invites USERS "u2" and "u3";
    USER "u1" creates a project and shares it with "g1";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of the users in the "g1" will become the new owner of the project and "u1" will be deleted
    """
    u1 = await login_user(client, exit_stack=exit_stack)
    u2 = await login_user(client, exit_stack=exit_stack)
    u3 = await login_user(client, exit_stack=exit_stack)

    # creating g1 and inviting u2 and u3
    g1 = await get_group(client, u1)
    await invite_user_to_group(client, owner=u1, invitee=u2, group=g1)
    await invite_user_to_group(client, owner=u1, invitee=u3, group=g1)

    # u1 creates project and shares it with g1
    project = await create_standard_project(
        client,
        u1,
        osparc_product_name,
        tests_data_dir,
        access_rights={str(g1["gid"]): {"read": True, "write": True, "delete": False}},
        exit_stack=exit_stack,
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    await assert_users_count(aiopg_engine, 3)
    await assert_projects_count(aiopg_engine, 1)
    await assert_user_is_owner_of_project(aiopg_engine, u1, project)

    await asyncio.sleep(2 * WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    await assert_user_not_in_db(aiopg_engine, u1)
    await assert_one_owner_for_project(aiopg_engine, project, [u2, u3])


async def test_t5_project_shared_with_other_users_transferred_to_one_of_them(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """
    USER "u1" creates a project and shares it with "u2" and "u3";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of "u2" or "u3" will become the new owner of the project and "u1" will be deleted
    """
    u1 = await login_user(client, exit_stack=exit_stack)
    u2 = await login_user(client, exit_stack=exit_stack)
    u3 = await login_user(client, exit_stack=exit_stack)

    q_u2 = await fetch_user_from_db(aiopg_engine, u2)
    assert q_u2
    q_u3 = await fetch_user_from_db(aiopg_engine, u3)
    assert q_u3

    # u1 creates project and shares it with g1
    project = await create_standard_project(
        client,
        u1,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
        access_rights={
            str(q_u2["primary_gid"]): {"read": True, "write": True, "delete": False},
            str(q_u3["primary_gid"]): {"read": True, "write": True, "delete": False},
        },
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    await assert_users_count(aiopg_engine, 3)
    await assert_projects_count(aiopg_engine, 1)
    await assert_user_is_owner_of_project(aiopg_engine, u1, project)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    await assert_user_not_in_db(aiopg_engine, u1)
    await assert_one_owner_for_project(aiopg_engine, project, [u2, u3])


async def test_t6_project_shared_with_group_transferred_to_last_user_in_group_on_owner_removal(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """
    USER "u1" creates a GROUP "g1" and invites USERS "u2" and "u3";
    USER "u1" creates a project and shares it with "g1";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of the users in the "g1" will become the new owner of the project and "u1" will be deleted
    the new owner either "u2" or "u3" will be manually marked as "GUEST";
    EXPECTED: the GUEST user will be deleted and the project will pass to the last member of "g1"
    """
    u1 = await login_user(client, exit_stack=exit_stack)
    u2 = await login_user(client, exit_stack=exit_stack)
    u3 = await login_user(client, exit_stack=exit_stack)

    # creating g1 and inviting u2 and u3
    g1 = await get_group(client, u1)
    await invite_user_to_group(client, owner=u1, invitee=u2, group=g1)
    await invite_user_to_group(client, owner=u1, invitee=u3, group=g1)

    # u1 creates project and shares it with g1
    project = await create_standard_project(
        client,
        u1,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
        access_rights={str(g1["gid"]): {"read": True, "write": True, "delete": False}},
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    await assert_users_count(aiopg_engine, 3)
    await assert_projects_count(aiopg_engine, 1)
    await assert_user_is_owner_of_project(aiopg_engine, u1, project)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    await assert_user_not_in_db(aiopg_engine, u1)
    await assert_one_owner_for_project(aiopg_engine, project, [u2, u3])

    # find new owner and mark hims as GUEST
    q_u2 = await fetch_user_from_db(aiopg_engine, u2)
    q_u3 = await fetch_user_from_db(aiopg_engine, u3)
    q_project = await fetch_project_from_db(aiopg_engine, project)

    new_owner = None
    remaining_others = []
    for user in [q_u2, q_u3]:
        assert user
        if user["id"] == q_project["prj_owner"]:
            new_owner = user
        else:
            remaining_others.append(user)

    assert new_owner is not None  # expected to a new owner between the 2 other users
    # mark new owner as guest
    await change_user_role(aiopg_engine, new_owner, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the new_owner will be deleted and one of the remainint_others wil be the new owner
    await assert_user_not_in_db(aiopg_engine, new_owner)
    await assert_one_owner_for_project(aiopg_engine, project, remaining_others)


async def test_t7_project_shared_with_group_transferred_from_one_member_to_the_last_and_all_is_removed(
    disable_garbage_collector_task: None,
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """
    USER "u1" creates a GROUP "g1" and invites USERS "u2" and "u3";
    USER "u1" creates a project and shares it with "g1";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of the users in the "g1" will become the new owner of the project and "u1" will be deleted
    the new owner either "u2" or "u3" will be manually marked as "GUEST";
    EXPECTED: the GUEST user will be deleted and the project will pass to the last member of "g1"
    afterwards the last user will be marked as "GUEST";
    EXPECTED: the last user will be removed and the project will be removed
    """
    assert client.app
    u1 = await login_user(client, exit_stack=exit_stack)
    u2 = await login_user(client, exit_stack=exit_stack)
    u3 = await login_user(client, exit_stack=exit_stack)

    # creating g1 and inviting u2 and u3
    g1 = await get_group(client, u1)
    await invite_user_to_group(client, owner=u1, invitee=u2, group=g1)
    await invite_user_to_group(client, owner=u1, invitee=u3, group=g1)

    # u1 creates project and shares it with g1
    project = await create_standard_project(
        client,
        u1,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
        access_rights={str(g1["gid"]): {"read": True, "write": True, "delete": False}},
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    await assert_projects_count(aiopg_engine, 1)
    await assert_users_count(aiopg_engine, 3)
    await assert_user_is_owner_of_project(aiopg_engine, u1, project)

    # await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)
    await gc_core.collect_garbage(app=client.app)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    await assert_one_owner_for_project(aiopg_engine, project, [u2, u3])
    await assert_user_not_in_db(aiopg_engine, u1)

    # find new owner and mark hims as GUEST
    q_u2 = await fetch_user_from_db(aiopg_engine, u2)
    q_u3 = await fetch_user_from_db(aiopg_engine, u3)
    q_project = await fetch_project_from_db(aiopg_engine, project)
    assert q_project

    new_owner: UserInfoDict | None = None
    remaining_users = []
    for user in [q_u2, q_u3]:
        assert user
        if user["id"] == q_project["prj_owner"]:
            new_owner = user
        else:
            remaining_users.append(user)

    assert new_owner is not None  # expected to a new owner between the 2 other users
    # mark new owner as guest
    await change_user_role(aiopg_engine, new_owner, UserRole.GUEST)

    # await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)
    await gc_core.collect_garbage(app=client.app)

    # expected outcome: the new_owner will be deleted and one of the remainint_others wil be the new owner
    await assert_one_owner_for_project(aiopg_engine, project, remaining_users)
    await assert_user_not_in_db(aiopg_engine, new_owner)

    # only 1 user is left as the owner mark him as GUEST
    for user in remaining_users:
        # mark new owner as guest
        await change_user_role(aiopg_engine, user, UserRole.GUEST)

    # await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)
    await gc_core.collect_garbage(app=client.app)

    # expected outcome: the last user will be removed and the project will be removed
    await assert_projects_count(aiopg_engine, 0)
    await assert_users_count(aiopg_engine, 0)


async def test_t8_project_shared_with_other_users_transferred_to_one_of_them_until_one_user_remains(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """
    USER "u1" creates a project and shares it with "u2" and "u3";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of "u2" or "u3" will become the new owner of the project and "u1" will be deleted
    same as T5 => afterwards afterwards the new owner either "u2" or "u3" will be manually marked as "GUEST";
    EXPECTED: the GUEST user will be deleted and the project will pass to the last member of "g1"
    """
    u1 = await login_user(client, exit_stack=exit_stack)
    u2 = await login_user(client, exit_stack=exit_stack)
    u3 = await login_user(client, exit_stack=exit_stack)

    q_u2 = await fetch_user_from_db(aiopg_engine, u2)
    assert q_u2
    q_u3 = await fetch_user_from_db(aiopg_engine, u3)
    assert q_u3

    # u1 creates project and shares it with g1
    project = await create_standard_project(
        client,
        u1,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
        access_rights={
            str(q_u2["primary_gid"]): {"read": True, "write": True, "delete": False},
            str(q_u3["primary_gid"]): {"read": True, "write": True, "delete": False},
        },
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    await assert_users_count(aiopg_engine, 3)
    await assert_projects_count(aiopg_engine, 1)
    await assert_user_is_owner_of_project(aiopg_engine, u1, project)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    await assert_user_not_in_db(aiopg_engine, u1)
    await assert_one_owner_for_project(aiopg_engine, project, [u2, u3])

    # find new owner and mark hims as GUEST
    q_u2 = await fetch_user_from_db(aiopg_engine, u2)
    q_u3 = await fetch_user_from_db(aiopg_engine, u3)
    q_project = await fetch_project_from_db(aiopg_engine, project)

    new_owner = None
    remaining_others = []
    for user in [q_u2, q_u3]:
        assert user
        if user["id"] == q_project["prj_owner"]:
            new_owner = user
        else:
            remaining_others.append(user)

    assert new_owner is not None  # expected to a new owner between the 2 other users
    # mark new owner as guest
    await change_user_role(aiopg_engine, new_owner, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the new_owner will be deleted and one of the remainint_others wil be the new owner
    await assert_user_not_in_db(aiopg_engine, new_owner)
    await assert_one_owner_for_project(aiopg_engine, project, remaining_others)
    await assert_users_count(aiopg_engine, 1)
    await assert_projects_count(aiopg_engine, 1)


async def test_t9_project_shared_with_other_users_transferred_between_them_and_then_removed(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """
    USER "u1" creates a project and shares it with "u2" and "u3";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of "u2" or "u3" will become the new owner of the project and "u1" will be deleted
    same as T5 => afterwards afterwards the new owner either "u2" or "u3" will be manually marked as "GUEST";
    EXPECTED: the GUEST user will be deleted and the project will pass to the last member of "g1"
    same as T8 => afterwards the last user will be marked as "GUEST";
    EXPECTED: the last user will be removed and the project will be removed
    """
    u1 = await login_user(client, exit_stack=exit_stack)
    u2 = await login_user(client, exit_stack=exit_stack)
    u3 = await login_user(client, exit_stack=exit_stack)

    q_u2 = await fetch_user_from_db(aiopg_engine, u2)
    assert q_u2
    q_u3 = await fetch_user_from_db(aiopg_engine, u3)
    assert q_u3

    # u1 creates project and shares it with g1
    project = await create_standard_project(
        client,
        u1,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
        access_rights={
            str(q_u2["primary_gid"]): {"read": True, "write": True, "delete": False},
            str(q_u3["primary_gid"]): {"read": True, "write": True, "delete": False},
        },
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    await assert_users_count(aiopg_engine, 3)
    await assert_projects_count(aiopg_engine, 1)
    await assert_user_is_owner_of_project(aiopg_engine, u1, project)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    await assert_user_not_in_db(aiopg_engine, u1)
    await assert_one_owner_for_project(aiopg_engine, project, [u2, u3])

    # find new owner and mark hims as GUEST
    q_u2 = await fetch_user_from_db(aiopg_engine, u2)
    q_u3 = await fetch_user_from_db(aiopg_engine, u3)
    q_project = await fetch_project_from_db(aiopg_engine, project)

    new_owner = None
    remaining_others = []
    for user in [q_u2, q_u3]:
        assert user
        if user["id"] == q_project["prj_owner"]:
            new_owner = user
        else:
            remaining_others.append(user)

    assert new_owner is not None  # expected to a new owner between the 2 other users
    # mark new owner as guest
    await change_user_role(aiopg_engine, new_owner, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the new_owner will be deleted and one of the remainint_others wil be the new owner
    await assert_user_not_in_db(aiopg_engine, new_owner)
    await assert_one_owner_for_project(aiopg_engine, project, remaining_others)
    await assert_users_count(aiopg_engine, 1)
    await assert_projects_count(aiopg_engine, 1)

    # only 1 user is left as the owner mark him as GUEST
    for user in remaining_others:
        # mark new owner as guest
        await change_user_role(aiopg_engine, user, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the last user will be removed and the project will be removed
    await assert_users_count(aiopg_engine, 0)
    await assert_projects_count(aiopg_engine, 0)


async def test_t10_owner_and_all_shared_users_marked_as_guests(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """
    USER "u1" creates a project and shares it with "u2" and "u3";
    USER "u1", "u2" and "u3" are manually marked as "GUEST";
    EXPECTED: the project and all the users are removed
    """

    gc_task: asyncio.Task = next(
        task for task in asyncio.all_tasks() if task.get_name() == _GC_TASK_NAME
    )
    assert not gc_task.done()

    u1 = await login_user(client, exit_stack=exit_stack)
    u2 = await login_user(client, exit_stack=exit_stack)
    u3 = await login_user(client, exit_stack=exit_stack)

    q_u2 = await fetch_user_from_db(aiopg_engine, u2)
    q_u3 = await fetch_user_from_db(aiopg_engine, u3)
    assert q_u2
    assert q_u3

    # u1 creates project and shares it with g1
    project = await create_standard_project(
        client,
        u1,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
        access_rights={
            str(q_u2["primary_gid"]): {"read": True, "write": True, "delete": False},
            str(q_u3["primary_gid"]): {"read": True, "write": True, "delete": False},
        },
    )

    # mark all users as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)
    await change_user_role(aiopg_engine, u2, UserRole.GUEST)
    await change_user_role(aiopg_engine, u3, UserRole.GUEST)

    await assert_users_count(aiopg_engine, 3)
    await assert_projects_count(aiopg_engine, 1)
    await assert_user_is_owner_of_project(aiopg_engine, u1, project)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    await assert_users_count(aiopg_engine, 0)
    await assert_projects_count(aiopg_engine, 0)


async def test_t11_owner_and_all_users_in_group_marked_as_guests(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    tests_data_dir: Path,
    osparc_product_name: str,
    exit_stack: contextlib.AsyncExitStack,
):
    """
    USER "u1" creates a group and invites "u2" and "u3";
    USER "u1" creates a project and shares it with the group
    USER "u1", "u2" and "u3" are manually marked as "GUEST"
    EXPECTED: the project and all the users are removed
    """
    u1 = await login_user(client, exit_stack=exit_stack)
    u2 = await login_user(client, exit_stack=exit_stack)
    u3 = await login_user(client, exit_stack=exit_stack)

    # creating g1 and inviting u2 and u3
    g1 = await get_group(client, u1)
    await invite_user_to_group(client, owner=u1, invitee=u2, group=g1)
    await invite_user_to_group(client, owner=u1, invitee=u3, group=g1)

    # u1 creates project and shares it with g1
    project = await create_standard_project(
        client,
        u1,
        osparc_product_name,
        tests_data_dir,
        exit_stack=exit_stack,
        access_rights={str(g1["gid"]): {"read": True, "write": True, "delete": False}},
    )

    # mark all users as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)
    await change_user_role(aiopg_engine, u2, UserRole.GUEST)
    await change_user_role(aiopg_engine, u3, UserRole.GUEST)

    await assert_users_count(aiopg_engine, 3)
    await assert_projects_count(aiopg_engine, 1)
    await assert_user_is_owner_of_project(aiopg_engine, u1, project)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    await assert_users_count(aiopg_engine, 0)
    await assert_projects_count(aiopg_engine, 0)
