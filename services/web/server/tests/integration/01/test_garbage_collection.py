# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
import re
from copy import deepcopy
from typing import Callable, Dict, List
from uuid import uuid4

import aiopg
import aioredis
import pytest
from aioresponses import aioresponses
from models_library.projects_state import RunningState
from models_library.settings.redis import RedisConfig
from pytest_simcore.helpers.utils_login import log_client_in
from pytest_simcore.helpers.utils_projects import create_project, empty_project_data
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.db_models import projects, users
from simcore_service_webserver.director.module_setup import setup_director
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.groups_api import (
    add_user_in_group,
    create_user_group,
    list_user_groups,
)
from simcore_service_webserver.login.module_setup import setup_login
from simcore_service_webserver.projects.module_setup import setup_projects
from simcore_service_webserver.resource_manager import garbage_collector
from simcore_service_webserver.resource_manager.module_setup import (
    setup_resource_manager,
)
from simcore_service_webserver.resource_manager.registry import get_registry
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio.module_setup import setup_socketio
from simcore_service_webserver.users import setup_users

log = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "redis",
    "storage",
]
pytest_simcore_ops_services_selection = ["minio"]


API_VERSION = "v0"
GARBAGE_COLLECTOR_INTERVAL = 1
SERVICE_DELETION_DELAY = 1
# ensure enough time has passed and GC was triggered
WAIT_FOR_COMPLETE_GC_CYCLE = GARBAGE_COLLECTOR_INTERVAL + SERVICE_DELETION_DELAY + 2


@pytest.fixture(autouse=True)
def __drop_and_recreate_postgres__(database_from_template_before_each_function) -> None:
    yield


@pytest.fixture(autouse=True)
async def __delete_all_redis_keys__(redis_service: RedisConfig):
    client = await aioredis.create_redis_pool(redis_service.dsn, encoding="utf-8")
    await client.flushall()
    client.close()
    await client.wait_closed()

    yield
    # do nothing on teadown


@pytest.fixture
async def director_v2_service_mock() -> aioresponses:
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
    # NOTE: GitHK I have to copy paste that fixture for some unclear reason for now.
    # I think this is due to some conflict between these non-pytest-simcore fixtures and the loop fixture being defined at different locations?? not sure..
    # anyway I think this should disappear once the garbage collector moves to its own micro-service
    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        mock.get(
            get_computation_pattern,
            status=202,
            payload={"state": str(RunningState.NOT_STARTED.value)},
            repeat=True,
        )
        mock.delete(delete_computation_pattern, status=204, repeat=True)
        yield mock


@pytest.fixture(autouse=True)
async def auto_mock_director_v2(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    return director_v2_service_mock


@pytest.fixture
def client(
    loop, aiohttp_client, app_config, postgres_with_template_db, mock_orphaned_services
):
    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VERSION
    assert cfg["rest"]["enabled"]
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True
    cfg["resource_manager"][
        "garbage_collection_interval_seconds"
    ] = GARBAGE_COLLECTOR_INTERVAL  # increase speed of garbage collection
    cfg["resource_manager"][
        "resource_deletion_timeout_seconds"
    ] = SERVICE_DELETION_DELAY  # reduce deletion delay

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
    assert setup_resource_manager(app)

    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


################ utils


async def login_user(client):
    """returns a logged in regular user"""
    return await log_client_in(client=client, user_data={"role": UserRole.USER.name})


async def login_guest_user(client):
    """returns a logged in Guest user"""
    return await log_client_in(client=client, user_data={"role": UserRole.GUEST.name})


async def new_project(client, user, access_rights=None):
    """returns a project for the given user"""
    project_data = empty_project_data()
    if access_rights is not None:
        project_data["accessRights"] = access_rights
    return await create_project(client.app, project_data, user["id"])


async def get_template_project(client, user, project_data: Dict, access_rights=None):
    """returns a tempalte shared with all"""
    _, _, all_group = await list_user_groups(client.app, user["id"])

    # the information comes from a file, randomize it
    project_data["name"] = "Fake template" + str(uuid4())
    project_data["uuid"] = str(uuid4())
    project_data["accessRights"] = {
        str(all_group["gid"]): {"read": True, "write": False, "delete": False}
    }
    if access_rights is not None:
        project_data["accessRights"].update(access_rights)

    return await create_project(client.app, project_data, user["id"])


async def get_group(client, user):
    """Creates a group for a given user"""
    return await create_user_group(
        app=client.app,
        user_id=user["id"],
        new_group={"label": uuid4(), "description": uuid4(), "thumbnail": None},
    )


async def invite_user_to_group(client, owner, invitee, group):
    """Invite a user to a group on which the owner has writes over"""
    await add_user_in_group(
        client.app,
        owner["id"],
        group["gid"],
        new_user_id=invitee["id"],
    )


async def change_user_role(
    aiopg_engine: aiopg.sa.Engine, user: Dict, role: UserRole
) -> None:
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            users.update().where(users.c.id == int(user["id"])).values(role=role.value)
        )


async def connect_to_socketio(client, user, socketio_client_factory: Callable):
    """Connect a user to a socket.io"""
    socket_registry = get_registry(client.server.app)
    cur_client_session_id = str(uuid4())
    sio = await socketio_client_factory(cur_client_session_id, client)
    resource_key = {
        "user_id": str(user["id"]),
        "client_session_id": cur_client_session_id,
    }
    assert await socket_registry.find_keys(("socket_id", sio.sid)) == [resource_key]
    assert sio.sid in await socket_registry.find_resources(resource_key, "socket_id")
    assert len(await socket_registry.find_resources(resource_key, "socket_id")) == 1
    sio_connection_data = sio, resource_key
    return sio_connection_data


async def disconnect_user_from_socketio(client, sio_connection_data):
    """disconnect a previously connected socket.io connection"""
    sio, resource_key = sio_connection_data
    sid = sio.sid
    socket_registry = get_registry(client.server.app)
    await sio.disconnect()
    assert not sio.sid
    assert not await socket_registry.find_keys(("socket_id", sio.sid))
    assert not sid in await socket_registry.find_resources(resource_key, "socket_id")
    assert not await socket_registry.find_resources(resource_key, "socket_id")


async def assert_users_count(
    aiopg_engine: aiopg.sa.Engine, expected_users: int
) -> bool:
    async with aiopg_engine.acquire() as conn:
        users_count = await conn.scalar(users.count())
        assert users_count == expected_users
        return True


async def assert_projects_count(
    aiopg_engine: aiopg.sa.Engine, expected_projects: int
) -> bool:
    async with aiopg_engine.acquire() as conn:
        projects_count = await conn.scalar(projects.count())
        assert projects_count == expected_projects
        return True


def assert_dicts_match_by_common_keys(first_dict, second_dict) -> bool:
    common_keys = set(first_dict.keys()) & set(second_dict.keys())
    for key in common_keys:
        assert first_dict[key] == second_dict[key], key

    return True


async def query_user_from_db(aiopg_engine: aiopg.sa.Engine, user: Dict):
    """returns a user from the db"""
    async with aiopg_engine.acquire() as conn:
        user_result = await conn.execute(
            users.select().where(users.c.id == int(user["id"]))
        )
        return await user_result.first()


async def query_project_from_db(aiopg_engine: aiopg.sa.Engine, user_project: Dict):
    async with aiopg_engine.acquire() as conn:
        project_result = await conn.execute(
            projects.select().where(projects.c.uuid == user_project["uuid"])
        )
        return await project_result.first()


async def assert_user_in_database(
    aiopg_engine: aiopg.sa.Engine, logged_user: Dict
) -> bool:
    user = await query_user_from_db(aiopg_engine, logged_user)
    user_as_dict = dict(user)

    # some values need to be transformed
    user_as_dict["role"] = user_as_dict["role"].value
    user_as_dict["status"] = user_as_dict["status"].value

    assert assert_dicts_match_by_common_keys(user_as_dict, logged_user) is True

    return True


async def assert_user_not_in_database(
    aiopg_engine: aiopg.sa.Engine, user: Dict
) -> bool:
    user = await query_user_from_db(aiopg_engine, user)
    assert user is None

    return True


async def assert_project_in_database(
    aiopg_engine: aiopg.sa.Engine, user_project: Dict
) -> bool:
    project = await query_project_from_db(aiopg_engine, user_project)
    project_as_dict = dict(project)

    assert assert_dicts_match_by_common_keys(project_as_dict, user_project) is True

    return True


async def assert_user_is_owner_of_project(
    aiopg_engine: aiopg.sa.Engine, owner_user: Dict, owner_project: Dict
) -> bool:
    user = await query_user_from_db(aiopg_engine, owner_user)
    project = await query_project_from_db(aiopg_engine, owner_project)

    assert user.id == project.prj_owner

    return True


async def assert_one_owner_for_project(
    aiopg_engine: aiopg.sa.Engine, project: Dict, possible_owners: List[Dict]
) -> bool:
    q_owners = [
        await query_user_from_db(aiopg_engine, owner) for owner in possible_owners
    ]
    q_project = await query_project_from_db(aiopg_engine, project)

    assert q_project.prj_owner in set([x.id for x in q_owners])

    return True


################ end utils


@pytest.fixture
def mock_garbage_collector_task(mocker):
    """patch the setup of the garbage collector so we can call it manually"""
    mocker.patch(
        "simcore_service_webserver.resource_manager.module_setup.setup_garbage_collector",
        return_value="",
    )


async def test_t1_while_guest_is_connected_no_resources_are_removed(
    mock_garbage_collector_task,
    client,
    socketio_client_factory: Callable,
    aiopg_engine,
    redis_client,
):
    """while a GUEST user is connected GC will not remove none of its projects nor the user itself"""
    logged_guest_user = await login_guest_user(client)
    empty_guest_user_project = await new_project(client, logged_guest_user)
    assert await assert_users_count(aiopg_engine, 1) is True
    assert await assert_projects_count(aiopg_engine, 1) is True

    await connect_to_socketio(client, logged_guest_user, socketio_client_factory)
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(app=client.app)

    assert await assert_user_in_database(aiopg_engine, logged_guest_user) is True
    assert (
        await assert_project_in_database(aiopg_engine, empty_guest_user_project) is True
    )


async def test_t2_cleanup_resources_after_browser_is_closed(
    mock_garbage_collector_task,
    simcore_services_ready,
    client,
    socketio_client_factory: Callable,
    aiopg_engine,
    redis_client,
):
    """After a GUEST users with one opened project closes browser tab regularly (GC cleans everything)"""
    logged_guest_user = await login_guest_user(client)
    empty_guest_user_project = await new_project(client, logged_guest_user)
    assert await assert_users_count(aiopg_engine, 1) is True
    assert await assert_projects_count(aiopg_engine, 1) is True

    sio_connection_data = await connect_to_socketio(
        client, logged_guest_user, socketio_client_factory
    )
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(app=client.app)

    # check user and project are still in the DB
    assert await assert_user_in_database(aiopg_engine, logged_guest_user) is True
    assert (
        await assert_project_in_database(aiopg_engine, empty_guest_user_project) is True
    )

    await disconnect_user_from_socketio(client, sio_connection_data)
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await garbage_collector.collect_garbage(app=client.app)

    # check user and project are no longer in the DB
    async with aiopg_engine.acquire() as conn:
        user_result = await conn.execute(users.select())
        user = await user_result.first()
        project_result = await conn.execute(projects.select())
        project = await project_result.first()

        assert user is None
        assert project is None


async def test_t3_gc_will_not_intervene_for_regular_users_and_their_resources(
    simcore_services_ready,
    client,
    socketio_client_factory: Callable,
    aiopg_engine,
    fake_project: Dict,
):
    """after a USER disconnects the GC will remove none of its projects or templates nor the user itself"""
    number_of_projects = 5
    number_of_templates = 5
    logged_user = await login_user(client)
    user_projects = [
        await new_project(client, logged_user) for _ in range(number_of_projects)
    ]
    user_template_projects = [
        await get_template_project(client, logged_user, fake_project)
        for _ in range(number_of_templates)
    ]

    async def assert_projects_and_users_are_present():
        # check user and projects and templates are still in the DB
        assert await assert_user_in_database(aiopg_engine, logged_user) is True
        for project in user_projects:
            assert await assert_project_in_database(aiopg_engine, project) is True
        for template in user_template_projects:
            assert await assert_project_in_database(aiopg_engine, template) is True

    assert await assert_users_count(aiopg_engine, 1) is True
    expected_count = number_of_projects + number_of_templates
    assert await assert_projects_count(aiopg_engine, expected_count) is True

    # connect the user and wait for gc
    sio_connection_data = await connect_to_socketio(
        client, logged_user, socketio_client_factory
    )
    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    await assert_projects_and_users_are_present()

    await disconnect_user_from_socketio(client, sio_connection_data)
    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    await assert_projects_and_users_are_present()


async def test_t4_project_shared_with_group_transferred_to_user_in_group_on_owner_removal(
    simcore_services_ready, client, aiopg_engine
):
    """
    USER "u1" creates a GROUP "g1" and invites USERS "u2" and "u3";
    USER "u1" creates a project and shares it with "g1";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of the users in the "g1" will become the new owner of the project and "u1" will be deleted
    """
    u1 = await login_user(client)
    u2 = await login_user(client)
    u3 = await login_user(client)

    # creating g1 and inviting u2 and u3
    g1 = await get_group(client, u1)
    await invite_user_to_group(client, owner=u1, invitee=u2, group=g1)
    await invite_user_to_group(client, owner=u1, invitee=u3, group=g1)

    # u1 creates project and shares it with g1
    project = await new_project(
        client,
        u1,
        access_rights={str(g1["gid"]): {"read": True, "write": True, "delete": False}},
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    assert await assert_users_count(aiopg_engine, 3) is True
    assert await assert_projects_count(aiopg_engine, 1) is True
    assert await assert_user_is_owner_of_project(aiopg_engine, u1, project) is True

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    assert await assert_user_not_in_database(aiopg_engine, u1) is True
    assert await assert_one_owner_for_project(aiopg_engine, project, [u2, u3]) is True


async def test_t5_project_shared_with_other_users_transferred_to_one_of_them(
    simcore_services_ready, client, aiopg_engine
):
    """
    USER "u1" creates a project and shares it with "u2" and "u3";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of "u2" or "u3" will become the new owner of the project and "u1" will be deleted
    """
    u1 = await login_user(client)
    u2 = await login_user(client)
    u3 = await login_user(client)

    q_u2 = await query_user_from_db(aiopg_engine, u2)
    q_u3 = await query_user_from_db(aiopg_engine, u3)

    # u1 creates project and shares it with g1
    project = await new_project(
        client,
        u1,
        access_rights={
            str(q_u2.primary_gid): {"read": True, "write": True, "delete": False},
            str(q_u3.primary_gid): {"read": True, "write": True, "delete": False},
        },
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    assert await assert_users_count(aiopg_engine, 3) is True
    assert await assert_projects_count(aiopg_engine, 1) is True
    assert await assert_user_is_owner_of_project(aiopg_engine, u1, project) is True

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    assert await assert_user_not_in_database(aiopg_engine, u1) is True
    assert await assert_one_owner_for_project(aiopg_engine, project, [u2, u3]) is True


async def test_t6_project_shared_with_group_transferred_to_last_user_in_group_on_owner_removal(
    simcore_services_ready, client, aiopg_engine
):
    """
    USER "u1" creates a GROUP "g1" and invites USERS "u2" and "u3";
    USER "u1" creates a project and shares it with "g1";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of the users in the "g1" will become the new owner of the project and "u1" will be deleted
    the new owner either "u2" or "u3" will be manually marked as "GUEST";
    EXPECTED: the GUEST user will be deleted and the project will pass to the last member of "g1"
    """
    u1 = await login_user(client)
    u2 = await login_user(client)
    u3 = await login_user(client)

    # creating g1 and inviting u2 and u3
    g1 = await get_group(client, u1)
    await invite_user_to_group(client, owner=u1, invitee=u2, group=g1)
    await invite_user_to_group(client, owner=u1, invitee=u3, group=g1)

    # u1 creates project and shares it with g1
    project = await new_project(
        client,
        u1,
        access_rights={str(g1["gid"]): {"read": True, "write": True, "delete": False}},
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    assert await assert_users_count(aiopg_engine, 3) is True
    assert await assert_projects_count(aiopg_engine, 1) is True
    assert await assert_user_is_owner_of_project(aiopg_engine, u1, project) is True

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    assert await assert_user_not_in_database(aiopg_engine, u1) is True
    assert await assert_one_owner_for_project(aiopg_engine, project, [u2, u3]) is True

    # find new owner and mark hims as GUEST
    q_u2 = await query_user_from_db(aiopg_engine, u2)
    q_u3 = await query_user_from_db(aiopg_engine, u3)
    q_project = await query_project_from_db(aiopg_engine, project)

    new_owner = None
    remaining_others = []
    for user in [q_u2, q_u3]:
        if user.id == q_project.prj_owner:
            new_owner = user
        else:
            remaining_others.append(user)

    assert new_owner is not None  # expected to a new owner between the 2 other users
    # mark new owner as guest
    await change_user_role(aiopg_engine, new_owner, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the new_owner will be deleted and one of the remainint_others wil be the new owner
    assert await assert_user_not_in_database(aiopg_engine, new_owner) is True
    assert (
        await assert_one_owner_for_project(aiopg_engine, project, remaining_others)
        is True
    )


async def test_t7_project_shared_with_group_transferred_from_one_member_to_the_last_and_all_is_removed(
    simcore_services_ready, client, aiopg_engine
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
    u1 = await login_user(client)
    u2 = await login_user(client)
    u3 = await login_user(client)

    # creating g1 and inviting u2 and u3
    g1 = await get_group(client, u1)
    await invite_user_to_group(client, owner=u1, invitee=u2, group=g1)
    await invite_user_to_group(client, owner=u1, invitee=u3, group=g1)

    # u1 creates project and shares it with g1
    project = await new_project(
        client,
        u1,
        access_rights={str(g1["gid"]): {"read": True, "write": True, "delete": False}},
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    assert await assert_users_count(aiopg_engine, 3) is True
    assert await assert_projects_count(aiopg_engine, 1) is True
    assert await assert_user_is_owner_of_project(aiopg_engine, u1, project) is True

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    assert await assert_user_not_in_database(aiopg_engine, u1) is True
    assert await assert_one_owner_for_project(aiopg_engine, project, [u2, u3]) is True

    # find new owner and mark hims as GUEST
    q_u2 = await query_user_from_db(aiopg_engine, u2)
    q_u3 = await query_user_from_db(aiopg_engine, u3)
    q_project = await query_project_from_db(aiopg_engine, project)

    new_owner = None
    remaining_others = []
    for user in [q_u2, q_u3]:
        if user.id == q_project.prj_owner:
            new_owner = user
        else:
            remaining_others.append(user)

    assert new_owner is not None  # expected to a new owner between the 2 other users
    # mark new owner as guest
    await change_user_role(aiopg_engine, new_owner, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the new_owner will be deleted and one of the remainint_others wil be the new owner
    assert await assert_user_not_in_database(aiopg_engine, new_owner) is True
    assert (
        await assert_one_owner_for_project(aiopg_engine, project, remaining_others)
        is True
    )

    # only 1 user is left as the owner mark him as GUEST
    for user in remaining_others:
        # mark new owner as guest
        await change_user_role(aiopg_engine, user, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the last user will be removed and the project will be removed
    assert await assert_users_count(aiopg_engine, 0) is True
    assert await assert_projects_count(aiopg_engine, 0) is True


async def test_t8_project_shared_with_other_users_transferred_to_one_of_them_until_one_user_remains(
    simcore_services_ready, client, aiopg_engine
):
    """
    USER "u1" creates a project and shares it with "u2" and "u3";
    USER "u1" is manually marked as "GUEST";
    EXPECTED: one of "u2" or "u3" will become the new owner of the project and "u1" will be deleted
    same as T5 => afterwards afterwards the new owner either "u2" or "u3" will be manually marked as "GUEST";
    EXPECTED: the GUEST user will be deleted and the project will pass to the last member of "g1"
    """
    u1 = await login_user(client)
    u2 = await login_user(client)
    u3 = await login_user(client)

    q_u2 = await query_user_from_db(aiopg_engine, u2)
    q_u3 = await query_user_from_db(aiopg_engine, u3)

    # u1 creates project and shares it with g1
    project = await new_project(
        client,
        u1,
        access_rights={
            str(q_u2.primary_gid): {"read": True, "write": True, "delete": False},
            str(q_u3.primary_gid): {"read": True, "write": True, "delete": False},
        },
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    assert await assert_users_count(aiopg_engine, 3) is True
    assert await assert_projects_count(aiopg_engine, 1) is True
    assert await assert_user_is_owner_of_project(aiopg_engine, u1, project) is True

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    assert await assert_user_not_in_database(aiopg_engine, u1) is True
    assert await assert_one_owner_for_project(aiopg_engine, project, [u2, u3]) is True

    # find new owner and mark hims as GUEST
    q_u2 = await query_user_from_db(aiopg_engine, u2)
    q_u3 = await query_user_from_db(aiopg_engine, u3)
    q_project = await query_project_from_db(aiopg_engine, project)

    new_owner = None
    remaining_others = []
    for user in [q_u2, q_u3]:
        if user.id == q_project.prj_owner:
            new_owner = user
        else:
            remaining_others.append(user)

    assert new_owner is not None  # expected to a new owner between the 2 other users
    # mark new owner as guest
    await change_user_role(aiopg_engine, new_owner, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the new_owner will be deleted and one of the remainint_others wil be the new owner
    assert await assert_user_not_in_database(aiopg_engine, new_owner) is True
    assert (
        await assert_one_owner_for_project(aiopg_engine, project, remaining_others)
        is True
    )
    assert await assert_users_count(aiopg_engine, 1) is True
    assert await assert_projects_count(aiopg_engine, 1) is True


async def test_t9_project_shared_with_other_users_transferred_between_them_and_then_removed(
    simcore_services_ready, client, aiopg_engine
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
    u1 = await login_user(client)
    u2 = await login_user(client)
    u3 = await login_user(client)

    q_u2 = await query_user_from_db(aiopg_engine, u2)
    q_u3 = await query_user_from_db(aiopg_engine, u3)

    # u1 creates project and shares it with g1
    project = await new_project(
        client,
        u1,
        access_rights={
            str(q_u2.primary_gid): {"read": True, "write": True, "delete": False},
            str(q_u3.primary_gid): {"read": True, "write": True, "delete": False},
        },
    )

    # mark u1 as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)

    assert await assert_users_count(aiopg_engine, 3) is True
    assert await assert_projects_count(aiopg_engine, 1) is True
    assert await assert_user_is_owner_of_project(aiopg_engine, u1, project) is True

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: u1 was deleted, one of the users in g1 is the new owner
    assert await assert_user_not_in_database(aiopg_engine, u1) is True
    assert await assert_one_owner_for_project(aiopg_engine, project, [u2, u3]) is True

    # find new owner and mark hims as GUEST
    q_u2 = await query_user_from_db(aiopg_engine, u2)
    q_u3 = await query_user_from_db(aiopg_engine, u3)
    q_project = await query_project_from_db(aiopg_engine, project)

    new_owner = None
    remaining_others = []
    for user in [q_u2, q_u3]:
        if user.id == q_project.prj_owner:
            new_owner = user
        else:
            remaining_others.append(user)

    assert new_owner is not None  # expected to a new owner between the 2 other users
    # mark new owner as guest
    await change_user_role(aiopg_engine, new_owner, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the new_owner will be deleted and one of the remainint_others wil be the new owner
    assert await assert_user_not_in_database(aiopg_engine, new_owner) is True
    assert (
        await assert_one_owner_for_project(aiopg_engine, project, remaining_others)
        is True
    )
    assert await assert_users_count(aiopg_engine, 1) is True
    assert await assert_projects_count(aiopg_engine, 1) is True

    # only 1 user is left as the owner mark him as GUEST
    for user in remaining_others:
        # mark new owner as guest
        await change_user_role(aiopg_engine, user, UserRole.GUEST)

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    # expected outcome: the last user will be removed and the project will be removed
    assert await assert_users_count(aiopg_engine, 0) is True
    assert await assert_projects_count(aiopg_engine, 0) is True


async def test_t10_owner_and_all_shared_users_marked_as_guests(
    simcore_services_ready, client, aiopg_engine
):
    """
    USER "u1" creates a project and shares it with "u2" and "u3";
    USER "u1", "u2" and "u3" are manually marked as "GUEST";
    EXPECTED: the project and all the users are removed
    """
    u1 = await login_user(client)
    u2 = await login_user(client)
    u3 = await login_user(client)

    q_u2 = await query_user_from_db(aiopg_engine, u2)
    q_u3 = await query_user_from_db(aiopg_engine, u3)

    # u1 creates project and shares it with g1
    project = await new_project(
        client,
        u1,
        access_rights={
            str(q_u2.primary_gid): {"read": True, "write": True, "delete": False},
            str(q_u3.primary_gid): {"read": True, "write": True, "delete": False},
        },
    )

    # mark all users as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)
    await change_user_role(aiopg_engine, u2, UserRole.GUEST)
    await change_user_role(aiopg_engine, u3, UserRole.GUEST)

    assert await assert_users_count(aiopg_engine, 3) is True
    assert await assert_projects_count(aiopg_engine, 1) is True
    assert await assert_user_is_owner_of_project(aiopg_engine, u1, project) is True

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    assert await assert_users_count(aiopg_engine, 0) is True
    assert await assert_projects_count(aiopg_engine, 0) is True


async def test_t11_owner_and_all_users_in_group_marked_as_guests(
    simcore_services_ready, client, aiopg_engine
):
    """
    USER "u1" creates a group and invites "u2" and "u3";
    USER "u1" creates a project and shares it with the group
    USER "u1", "u2" and "u3" are manually marked as "GUEST"
    EXPECTED: the project and all the users are removed
    """
    u1 = await login_user(client)
    u2 = await login_user(client)
    u3 = await login_user(client)

    # creating g1 and inviting u2 and u3
    g1 = await get_group(client, u1)
    await invite_user_to_group(client, owner=u1, invitee=u2, group=g1)
    await invite_user_to_group(client, owner=u1, invitee=u3, group=g1)

    # u1 creates project and shares it with g1
    project = await new_project(
        client,
        u1,
        access_rights={str(g1["gid"]): {"read": True, "write": True, "delete": False}},
    )

    # mark all users as guest
    await change_user_role(aiopg_engine, u1, UserRole.GUEST)
    await change_user_role(aiopg_engine, u2, UserRole.GUEST)
    await change_user_role(aiopg_engine, u3, UserRole.GUEST)

    assert await assert_users_count(aiopg_engine, 3) is True
    assert await assert_projects_count(aiopg_engine, 1) is True
    assert await assert_user_is_owner_of_project(aiopg_engine, u1, project) is True

    await asyncio.sleep(WAIT_FOR_COMPLETE_GC_CYCLE)

    assert await assert_users_count(aiopg_engine, 0) is True
    assert await assert_projects_count(aiopg_engine, 0) is True
