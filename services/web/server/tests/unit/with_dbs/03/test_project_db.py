# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from copy import deepcopy
from random import randint
from secrets import choice
from typing import Any, get_args
from uuid import UUID, uuid5

import aiopg.sa
import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from psycopg2.errors import UniqueViolation
from pytest_simcore.helpers.dict_tools import copy_from_dict_ex
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict, log_client_in
from servicelib.utils import logged_gather
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo
from simcore_service_webserver.projects._db_utils import PermissionStr
from simcore_service_webserver.projects._groups_db import update_or_insert_project_group
from simcore_service_webserver.projects.api import has_user_project_access_rights
from simcore_service_webserver.projects.db import ProjectAccessRights, ProjectDBAPI
from simcore_service_webserver.projects.exceptions import (
    NodeNotFoundError,
    ProjectNodeRequiredInputsNotSetError,
    ProjectNotFoundError,
)
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.projects_api import (
    _check_project_node_has_all_required_inputs,
)
from simcore_service_webserver.users.exceptions import UserNotFoundError
from simcore_service_webserver.utils import to_datetime
from sqlalchemy.engine.result import Row


@pytest.fixture
def group_id() -> int:
    return 234


async def test_setup_projects_db(client: TestClient):
    assert client.app
    db_api = ProjectDBAPI.get_from_app_context(app=client.app)
    assert db_api
    assert isinstance(db_api, ProjectDBAPI)

    assert db_api._app == client.app  # noqa: SLF001
    assert db_api.engine


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # improve speed by using more clients
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {"POSTGRES_MAXSIZE": "80"},
    )
    return app_environment | envs_plugins


@pytest.fixture()
def db_api(client: TestClient, postgres_db: sa.engine.Engine) -> Iterator[ProjectDBAPI]:
    assert client.app
    db_api = ProjectDBAPI.get_from_app_context(app=client.app)

    yield db_api

    # clean the projects
    with postgres_db.connect() as conn:
        conn.execute(sa.DDL("DELETE FROM projects"))


def _assert_added_project(
    exp_project: dict[str, Any],
    added_project: dict[str, Any],
    exp_overrides: dict[str, Any],
):
    expected_prj = deepcopy(exp_project)
    added_prj = deepcopy(added_project)
    _DIFFERENT_KEYS = [
        "creationDate",
        "lastChangeDate",
        "accessRights",  # NOTE: access rights were moved away from the projects table
        "trashedAt",
        "trashedExplicitly",
    ]
    assert {k: v for k, v in expected_prj.items() if k in _DIFFERENT_KEYS} != {
        k: v for k, v in added_prj.items() if k in _DIFFERENT_KEYS
    }
    assert to_datetime(added_prj["creationDate"]) > to_datetime(
        expected_prj["creationDate"]
    )
    assert to_datetime(added_prj["creationDate"]) <= to_datetime(
        added_prj["lastChangeDate"]
    )
    expected_prj.update(exp_overrides)
    for k in _DIFFERENT_KEYS:
        added_prj.pop(k, None)
        expected_prj.pop(k, None)

    # the rest of the keys shall be the same as the original
    assert added_prj == expected_prj


def _assert_projects_to_product_db_row(
    postgres_db: sa.engine.Engine, project: dict[str, Any], product_name: str
):
    with postgres_db.connect() as conn:
        rows = conn.execute(
            sa.select(projects_to_products).where(
                projects_to_products.c.project_uuid == f"{project['uuid']}"
            )
        ).fetchall()
    assert rows
    assert len(rows) == 1
    assert rows[0][projects_to_products.c.product_name] == product_name


async def _assert_projects_nodes_db_rows(
    aiopg_engine: aiopg.sa.engine.Engine, project: dict[str, Any]
) -> None:
    async with aiopg_engine.acquire() as conn:
        repo = ProjectNodesRepo(project_uuid=ProjectID(f"{project['uuid']}"))
        list_of_nodes = await repo.list(conn)
        project_workbench = project.get("workbench", {})
        assert len(list_of_nodes) == len(project_workbench)
        new_style_node_ids = sorted(f"{node.node_id}" for node in list_of_nodes)
        old_style_node_ids = sorted(project_workbench.keys())
        assert new_style_node_ids == old_style_node_ids


def _assert_project_db_row(
    postgres_db: sa.engine.Engine, project: dict[str, Any], **kwargs
):
    with postgres_db.connect() as conn:
        row: Row | None = conn.execute(
            sa.select(projects).where(projects.c.uuid == f"{project['uuid']}")
        ).fetchone()

    expected_db_entries = {
        "type": ProjectType.STANDARD,
        "uuid": project["uuid"],
        "name": project["name"],
        "description": project["description"],
        "thumbnail": project["thumbnail"],
        "prj_owner": None,
        "workbench": project["workbench"],
        "published": False,
        "dev": project["dev"],
        "classifiers": project["classifiers"],
        "ui": project["ui"],
        "quality": project["quality"],
        "creation_date": to_datetime(project["creationDate"]),
        "last_change_date": to_datetime(project["lastChangeDate"]),
    }
    expected_db_entries.update(kwargs)
    assert row
    project_entries_in_db = {k: row[k] for k in expected_db_entries}
    assert project_entries_in_db == expected_db_entries
    assert row["last_change_date"] >= row["creation_date"]


@pytest.fixture
async def insert_project_in_db(
    aiopg_engine: aiopg.sa.engine.Engine,
    db_api: ProjectDBAPI,
    osparc_product_name: str,
    client: TestClient,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    inserted_projects = []

    async def _inserter(prj: dict[str, Any], **overrides) -> dict[str, Any]:
        # add project without user id -> by default creates a template
        default_config: dict[str, Any] = {
            "project": prj,
            "user_id": None,
            "product_name": osparc_product_name,
            "project_nodes": None,
        }
        default_config.update(**overrides)
        new_project = await db_api.insert_project(**default_config)
        if _access_rights := default_config["project"].get(
            "access_rights", {}
        ) | default_config["project"].get("accessRights", {}):
            for group_id, permissions in _access_rights.items():
                await update_or_insert_project_group(
                    client.app,
                    new_project["uuid"],
                    group_id=int(group_id),
                    read=permissions["read"],
                    write=permissions["write"],
                    delete=permissions["delete"],
                )

        inserted_projects.append(new_project["uuid"])
        return new_project

    yield _inserter

    print(f"<-- removing {len(inserted_projects)} projects...")
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            projects.delete().where(projects.c.uuid.in_(inserted_projects))
        )
    print(f"<-- removal of {len(inserted_projects)} projects done.")


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.USER),
    ],
)
async def test_insert_project_to_db(
    fake_project: dict[str, Any],
    postgres_db: sa.engine.Engine,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    osparc_product_name: str,
    aiopg_engine: aiopg.sa.engine.Engine,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
):
    expected_project = deepcopy(fake_project)

    # add project without user id -> by default creates a template
    new_project = await insert_project_in_db(fake_project)
    _assert_added_project(
        expected_project,
        new_project,
        exp_overrides={"prjOwner": "not_a_user@unknown.com"},
    )
    _assert_project_db_row(postgres_db, new_project, type=ProjectType.TEMPLATE)
    _assert_projects_to_product_db_row(postgres_db, new_project, osparc_product_name)
    await _assert_projects_nodes_db_rows(aiopg_engine, new_project)

    # adding a project with a fake user id raises
    fake_user_id = 4654654654

    with pytest.raises(UserNotFoundError):
        await insert_project_in_db(fake_project, user_id=fake_user_id)
    with pytest.raises(UserNotFoundError):
        # adding a project with a fake user but forcing as template should still raise
        await insert_project_in_db(
            expected_project,
            project=fake_project,
            user_id=fake_user_id,
            force_as_template=True,
        )

    # adding a project with a logged user does not raise and creates a STANDARD project
    # since we already have a project with that uuid, it shall be updated
    new_project = await insert_project_in_db(fake_project, user_id=logged_user["id"])
    assert new_project["uuid"] != expected_project["uuid"]
    _assert_added_project(
        expected_project,
        new_project,
        exp_overrides={
            "uuid": new_project["uuid"],
            "prjOwner": logged_user["email"],
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
    )
    _assert_projects_to_product_db_row(postgres_db, new_project, osparc_product_name)
    await _assert_projects_nodes_db_rows(aiopg_engine, new_project)

    # adding a project with a logged user and forcing as template, should create a TEMPLATE project owned by the user
    new_project = await insert_project_in_db(
        fake_project,
        user_id=logged_user["id"],
        force_as_template=True,
    )
    assert new_project["uuid"] != expected_project["uuid"]
    _assert_added_project(
        expected_project,
        new_project,
        exp_overrides={
            "uuid": new_project["uuid"],
            "prjOwner": logged_user["email"],
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
        type=ProjectType.TEMPLATE,
    )
    _assert_projects_to_product_db_row(postgres_db, new_project, osparc_product_name)
    await _assert_projects_nodes_db_rows(aiopg_engine, new_project)
    # add a project with a uuid that is already present, using force_project_uuid shall raise
    with pytest.raises(UniqueViolation):
        await insert_project_in_db(
            fake_project,
            user_id=logged_user["id"],
            force_project_uuid=True,
        )

    # add a project with a bad uuid that is already present, using force_project_uuid shall raise
    fake_project["uuid"] = "some bad uuid"
    with pytest.raises(ValueError):  # noqa: PT011
        await insert_project_in_db(
            fake_project,
            user_id=logged_user["id"],
            force_project_uuid=True,
        )

    # add a project with a bad uuid that is already present, shall not raise
    new_project = await insert_project_in_db(
        fake_project,
        user_id=logged_user["id"],
        force_project_uuid=False,
    )
    _assert_added_project(
        expected_project,
        new_project,
        exp_overrides={
            "uuid": new_project["uuid"],
            "prjOwner": logged_user["email"],
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
    )
    _assert_projects_to_product_db_row(postgres_db, new_project, osparc_product_name)
    await _assert_projects_nodes_db_rows(aiopg_engine, new_project)


@pytest.mark.parametrize(
    "user_role",
    [(UserRole.USER)],
)
async def test_patch_user_project_workbench_raises_if_project_does_not_exist(
    fake_project: dict[str, Any],
    logged_user: dict[str, Any],
    db_api: ProjectDBAPI,
    faker: Faker,
):
    partial_workbench_data = {
        faker.uuid4(): {
            "key": "simcore/services/comp/sleepers",
            "version": faker.numerify("%.#.#"),
            "label": "I am a test node",
        }
    }
    with pytest.raises(ProjectNotFoundError):
        await db_api._update_project_workbench(  # noqa: SLF001
            partial_workbench_data,
            user_id=logged_user["id"],
            project_uuid=fake_project["uuid"],
            allow_workbench_changes=False,
        )


@pytest.mark.parametrize(
    "user_role",
    [(UserRole.USER)],
)
async def test_patch_user_project_workbench_creates_nodes(
    fake_project: dict[str, Any],
    logged_user: dict[str, Any],
    db_api: ProjectDBAPI,
    faker: Faker,
    aiopg_engine: aiopg.sa.engine.Engine,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
):
    empty_fake_project = deepcopy(fake_project)
    workbench = empty_fake_project.setdefault("workbench", {})
    assert isinstance(workbench, dict)
    workbench.clear()
    new_project = await insert_project_in_db(
        empty_fake_project, user_id=logged_user["id"]
    )
    await _assert_projects_nodes_db_rows(aiopg_engine, new_project)
    partial_workbench_data = {
        faker.uuid4(): {
            "key": f"simcore/services/comp/{faker.pystr().lower()}",
            "version": faker.numerify("%.#.#"),
            "label": faker.text(),
        }
        for _ in range(faker.pyint(min_value=5, max_value=30))
    }
    (
        patched_project,
        changed_entries,
    ) = await db_api._update_project_workbench(  # noqa: SLF001
        partial_workbench_data,
        user_id=logged_user["id"],
        project_uuid=new_project["uuid"],
        allow_workbench_changes=True,
    )
    for node_id in partial_workbench_data:
        assert node_id in patched_project["workbench"]
        assert partial_workbench_data[node_id] == patched_project["workbench"][node_id]
        assert node_id in changed_entries
        assert changed_entries[node_id] == partial_workbench_data[node_id]


@pytest.mark.parametrize(
    "user_role",
    [(UserRole.USER)],
)
async def test_patch_user_project_workbench_creates_nodes_raises_if_invalid_node_is_passed(
    fake_project: dict[str, Any],
    logged_user: dict[str, Any],
    db_api: ProjectDBAPI,
    faker: Faker,
    aiopg_engine: aiopg.sa.engine.Engine,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
):
    empty_fake_project = deepcopy(fake_project)
    workbench = empty_fake_project.setdefault("workbench", {})
    assert isinstance(workbench, dict)
    workbench.clear()

    new_project = await insert_project_in_db(
        empty_fake_project, user_id=logged_user["id"]
    )
    await _assert_projects_nodes_db_rows(aiopg_engine, new_project)
    partial_workbench_data = {
        faker.uuid4(): {
            "version": faker.numerify("%.#.#"),
            "label": faker.text(),
        }
        for _ in range(faker.pyint(min_value=5, max_value=30))
    }
    with pytest.raises(NodeNotFoundError):
        await db_api._update_project_workbench(  # noqa: SLF001
            partial_workbench_data,
            user_id=logged_user["id"],
            project_uuid=new_project["uuid"],
            allow_workbench_changes=True,
        )


@pytest.mark.parametrize(
    "user_role",
    [(UserRole.USER)],
)
@pytest.mark.parametrize("number_of_nodes", [1, randint(250, 300)])  # noqa: S311
async def test_patch_user_project_workbench_concurrently(
    fake_project: dict[str, Any],
    postgres_db: sa.engine.Engine,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    db_api: ProjectDBAPI,
    number_of_nodes: int,
    aiopg_engine: aiopg.sa.engine.Engine,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
):
    _NUMBER_OF_NODES = number_of_nodes
    BASE_UUID = UUID("ccc0839f-93b8-4387-ab16-197281060927")
    node_uuids = [str(uuid5(BASE_UUID, f"{n}")) for n in range(_NUMBER_OF_NODES)]

    # create a project with a lot of nodes
    fake_project["workbench"] = {
        node_uuids[n]: {
            "key": "simcore/services/comp/sleepers",
            "version": "1.43.5",
            "label": f"I am node {n}",
        }
        for n in range(_NUMBER_OF_NODES)
    }
    expected_project = deepcopy(fake_project)

    # add the project
    original_project = deepcopy(fake_project)
    new_project = await insert_project_in_db(fake_project, user_id=logged_user["id"])

    _assert_added_project(
        original_project,
        new_project,
        exp_overrides={
            "prjOwner": logged_user["email"],
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
    )
    await _assert_projects_nodes_db_rows(aiopg_engine, new_project)

    # patch all the nodes concurrently
    randomly_created_outputs = [
        {
            "outputs": {f"out_{k}": f"{k}"}  # noqa: RUF011
            for k in range(randint(1, 10))  # noqa: S311
        }
        for n in range(_NUMBER_OF_NODES)
    ]
    for n in range(_NUMBER_OF_NODES):
        expected_project["workbench"][node_uuids[n]].update(randomly_created_outputs[n])

    patched_projects: list[
        tuple[dict[str, Any], dict[str, Any]]
    ] = await asyncio.gather(
        *[
            db_api._update_project_workbench(  # noqa: SLF001
                {NodeIDStr(node_uuids[n]): randomly_created_outputs[n]},
                user_id=logged_user["id"],
                project_uuid=new_project["uuid"],
                allow_workbench_changes=False,
            )
            for n in range(_NUMBER_OF_NODES)
        ]
    )
    # NOTE: each returned project contains the project with some updated workbenches
    # the ordering is uncontrolled.
    # The important thing is that the final result shall contain ALL the changes

    for (prj, changed_entries), node_uuid, exp_outputs in zip(
        patched_projects, node_uuids, randomly_created_outputs, strict=True
    ):
        assert prj["workbench"][node_uuid]["outputs"] == exp_outputs["outputs"]
        assert changed_entries == {node_uuid: {"outputs": exp_outputs["outputs"]}}

    # get the latest change date
    latest_change_date = max(
        to_datetime(prj["lastChangeDate"]) for prj, _ in patched_projects
    )

    # check the nodes are completely patched as expected
    _assert_project_db_row(
        postgres_db,
        expected_project,
        prj_owner=logged_user["id"],
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )

    # now concurrently remove the outputs
    for n in range(_NUMBER_OF_NODES):
        expected_project["workbench"][node_uuids[n]]["outputs"] = {}

    patched_projects = await asyncio.gather(
        *[
            db_api._update_project_workbench(  # noqa: SLF001
                {NodeIDStr(node_uuids[n]): {"outputs": {}}},
                user_id=logged_user["id"],
                project_uuid=new_project["uuid"],
                allow_workbench_changes=False,
            )
            for n in range(_NUMBER_OF_NODES)
        ]
    )

    # get the latest change date
    latest_change_date = max(
        to_datetime(prj["lastChangeDate"]) for prj, _ in patched_projects
    )

    # check the nodes are completely patched as expected
    _assert_project_db_row(
        postgres_db,
        expected_project,
        prj_owner=logged_user["id"],
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )

    # now concurrently remove the outputs
    for n in range(_NUMBER_OF_NODES):
        expected_project["workbench"][node_uuids[n]]["outputs"] = {}

    patched_projects = await asyncio.gather(
        *[
            db_api._update_project_workbench(  # noqa: SLF001
                {NodeIDStr(node_uuids[n]): {"outputs": {}}},
                user_id=logged_user["id"],
                project_uuid=new_project["uuid"],
                allow_workbench_changes=False,
            )
            for n in range(_NUMBER_OF_NODES)
        ]
    )

    # get the latest change date
    latest_change_date = max(
        to_datetime(prj["lastChangeDate"]) for prj, _ in patched_projects
    )

    # check the nodes are completely patched as expected
    _assert_project_db_row(
        postgres_db,
        expected_project,
        prj_owner=logged_user["id"],
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )


@pytest.fixture()
async def some_projects_and_nodes(
    logged_user: dict[str, Any],
    fake_project: dict[str, Any],
    aiopg_engine: aiopg.sa.engine.Engine,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[ProjectID, list[NodeID]]:
    """Will create a few projects, no need to go crazy here"""
    NUMBER_OF_PROJECTS = 17

    BASE_UUID = UUID("ccc0839f-93b8-4387-ab16-197281060927")
    all_created_projects = {}
    project_creation_tasks = []
    for p in range(NUMBER_OF_PROJECTS):
        project_uuid = uuid5(BASE_UUID, f"project_{p}")
        all_created_projects[project_uuid] = []
        workbench = {}
        for n in range(randint(7, 34)):  # noqa: S311
            node_uuid = uuid5(project_uuid, f"node_{n}")
            all_created_projects[project_uuid].append(node_uuid)
            workbench[f"{node_uuid}"] = {
                "key": "simcore/services/comp/sleepers",
                "version": "1.43.5",
                "label": f"I am node {n}",
            }
        new_project = deepcopy(fake_project)
        new_project.update(uuid=project_uuid, name=f"project {p}", workbench=workbench)
        # add the project
        project_creation_tasks.append(
            insert_project_in_db(
                new_project,
                user_id=logged_user["id"],
            )
        )

    created_projects = await logged_gather(*project_creation_tasks)
    await asyncio.gather(
        *(_assert_projects_nodes_db_rows(aiopg_engine, prj) for prj in created_projects)
    )
    print(f"---> created {len(all_created_projects)} projects in the database")
    return all_created_projects


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_node_id_exists(
    db_api: ProjectDBAPI, some_projects_and_nodes: dict[ProjectID, list[NodeID]]
):
    # create a node uuid that does not exist from an existing project
    existing_project_id = choice(list(some_projects_and_nodes.keys()))
    not_existing_node_id_in_existing_project = uuid5(
        existing_project_id, "node_invalid_node"
    )

    node_id_exists = await db_api.node_id_exists(
        not_existing_node_id_in_existing_project
    )
    assert node_id_exists is False
    existing_node_id = choice(some_projects_and_nodes[existing_project_id])
    node_id_exists = await db_api.node_id_exists(existing_node_id)
    assert node_id_exists is True


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_node_ids_from_project(
    db_api: ProjectDBAPI, some_projects_and_nodes: dict[ProjectID, list[NodeID]]
):
    node_ids_inside_project_list = await asyncio.gather(
        *(
            db_api.list_node_ids_in_project(project_id)
            for project_id in some_projects_and_nodes
        )
    )

    for project_id, node_ids_inside_project in zip(
        some_projects_and_nodes, node_ids_inside_project_list, strict=True
    ):
        assert node_ids_inside_project == set(some_projects_and_nodes[project_id])


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_replace_user_project(
    db_api: ProjectDBAPI,
    user_project: ProjectDict,
    logged_user: UserInfoDict,
    osparc_product_name: str,
    postgres_db: sa.engine.Engine,
    aiopg_engine: aiopg.sa.engine.Engine,
):
    PROJECT_DICT_IGNORE_FIELDS = {"lastChangeDate"}
    original_project = user_project
    # replace the project with the same should do nothing
    working_project = await db_api.replace_project(
        original_project,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        project_uuid=original_project["uuid"],
    )
    assert copy_from_dict_ex(
        original_project, PROJECT_DICT_IGNORE_FIELDS
    ) == copy_from_dict_ex(working_project, PROJECT_DICT_IGNORE_FIELDS)
    _assert_projects_to_product_db_row(
        postgres_db, working_project, osparc_product_name
    )
    await _assert_projects_nodes_db_rows(aiopg_engine, working_project)

    # now let's create some outputs (similar to what happens when running services)
    NODE_INDEX = 1  # this is not the file-picker
    node_id = tuple(working_project["workbench"].keys())[NODE_INDEX]
    node_data = working_project["workbench"][node_id]
    node_data["progress"] = 100
    node_data["outputs"] = {
        "output_1": {
            "store": 0,
            "path": "687b8dc2-fea2-11ec-b7fd-02420a6e3a4d/d61a2ec8-19b4-4375-adcb-fdd22f850333/single_number.txt",
            "eTag": "c4ca4238a0b923820dcc509a6f75849b",
        },
        "output_2": 5,
    }
    node_data[
        "runHash"
    ] = "5b0583fa546ac82f0e41cef9705175b7187ce3928ba42892e842add912c16676"
    # replacing with the new entries shall return the very same data
    replaced_project = await db_api.replace_project(
        working_project,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        project_uuid=working_project["uuid"],
    )
    assert copy_from_dict_ex(
        working_project, PROJECT_DICT_IGNORE_FIELDS
    ) == copy_from_dict_ex(replaced_project, PROJECT_DICT_IGNORE_FIELDS)
    _assert_projects_to_product_db_row(
        postgres_db, replaced_project, osparc_product_name
    )
    await _assert_projects_nodes_db_rows(aiopg_engine, replaced_project)

    # the frontend sends project without some fields, but for FRONTEND type of nodes
    # replacing should keep the values
    FRONTEND_EXCLUDED_FIELDS = ["outputs", "progress", "runHash"]
    incoming_frontend_project = deepcopy(original_project)
    for node_data in incoming_frontend_project["workbench"].values():
        if "frontend" not in node_data["key"]:
            for field in FRONTEND_EXCLUDED_FIELDS:
                node_data.pop(field, None)
    replaced_project = await db_api.replace_project(
        incoming_frontend_project,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        project_uuid=incoming_frontend_project["uuid"],
    )
    assert copy_from_dict_ex(
        working_project, PROJECT_DICT_IGNORE_FIELDS
    ) == copy_from_dict_ex(replaced_project, PROJECT_DICT_IGNORE_FIELDS)


@pytest.mark.parametrize("user_role", [UserRole.ANONYMOUS])  # worst case
@pytest.mark.parametrize("access_rights", [x.value for x in ProjectAccessRights])
async def test_has_permission(
    faker: Faker,
    logged_user: dict[str, Any],
    fake_project: dict[str, Any],
    db_api: ProjectDBAPI,
    access_rights: dict[str, bool],
    user_role: UserRole,
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
):
    project_id = faker.uuid4(cast_to=None)
    owner_id = logged_user["id"]

    second_user: UserInfoDict = await log_client_in(
        client=client, user_data={"role": UserRole.USER.name}
    )

    new_project = deepcopy(fake_project)
    new_project.update(
        uuid=project_id,
        access_rights={second_user["primary_gid"]: access_rights},
    )

    new_project = await insert_project_in_db(
        new_project,
        user_id=owner_id,
    )

    await _assert_projects_nodes_db_rows(aiopg_engine, new_project)
    for permission in get_args(PermissionStr):
        assert permission in access_rights

        # owner always is allowed to do everything
        # assert await db_api.has_permission(owner_id, project_id, permission) is True
        assert (
            await has_user_project_access_rights(
                client.app,
                project_id=project_id,
                user_id=owner_id,
                permission=permission,
            )
            is True
        )

        # user does not exits
        assert (
            await has_user_project_access_rights(
                client.app, project_id=project_id, user_id=-1, permission=permission
            )
            is False
        )

        # other user
        assert (
            await has_user_project_access_rights(
                client.app,
                project_id=project_id,
                user_id=second_user["id"],
                permission=permission,
            )
            is access_rights[permission]
        ), f"Found unexpected {permission=} for {access_rights=} of {user_role=} and {project_id=}"


def _fake_output_data() -> dict:
    return {
        "store": 0,
        "path": "9f8207e6-144a-11ef-831f-0242ac140027/98b68cbe-9e22-4eb5-a91b-2708ad5317b7/outputs/output_2/output_2.zip",
        "eTag": "ec3bc734d85359b660aab400147cd1ea",
    }


def _fake_connect_to(output_number: int) -> dict:
    return {
        "nodeUuid": "98b68cbe-9e22-4eb5-a91b-2708ad5317b7",
        "output": f"output_{output_number}",
    }


@pytest.fixture
async def inserted_project(
    logged_user: dict[str, Any],
    insert_project_in_db: Callable[..., Awaitable[dict[str, Any]]],
    fake_project: dict[str, Any],
    downstream_inputs: dict,
    downstream_required_inputs: list[str],
    upstream_outputs: dict,
) -> dict:
    fake_project["workbench"] = {
        "98b68cbe-9e22-4eb5-a91b-2708ad5317b7": {
            "key": "simcore/services/dynamic/jupyter-math",
            "version": "2.0.10",
            "label": "upstream",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "thumbnail": "",
            "outputs": upstream_outputs,
            "runHash": "c6ae58f36a2e0f65f443441ecda023a451cb1b8051d01412d79aa03653e1a6b3",
        },
        "324d6ef2-a82c-414d-9001-dc84da1cbea3": {
            "key": "simcore/services/dynamic/jupyter-math",
            "version": "2.0.10",
            "label": "downstream",
            "inputs": downstream_inputs,
            "inputsUnits": {},
            "inputNodes": ["98b68cbe-9e22-4eb5-a91b-2708ad5317b7"],
            "thumbnail": "",
            "inputsRequired": downstream_required_inputs,
        },
    }

    return await insert_project_in_db(fake_project, user_id=logged_user["id"])


@pytest.mark.parametrize(
    "downstream_inputs,downstream_required_inputs,upstream_outputs,expected_error",
    [
        pytest.param(
            {"input_1": _fake_connect_to(1)},
            ["input_1", "input_2"],
            {},
            "Missing 'input_2' connection(s) to 'downstream'",
            id="missing_connection_on_input_2",
        ),
        pytest.param(
            {"input_1": _fake_connect_to(1), "input_2": _fake_connect_to(2)},
            ["input_1", "input_2"],
            {"output_2": _fake_output_data()},
            "Missing: 'output_1' of 'upstream'",
            id="output_1_has_not_file",
        ),
    ],
)
@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_check_project_node_has_all_required_inputs_raises(
    client: TestClient,
    logged_user: dict[str, Any],
    db_api: ProjectDBAPI,
    inserted_project: dict,
    expected_error: str,
):

    with pytest.raises(ProjectNodeRequiredInputsNotSetError) as exc:
        await _check_project_node_has_all_required_inputs(
            client.app,
            db_api,
            user_id=logged_user["id"],
            project_uuid=UUID(inserted_project["uuid"]),
            node_id=UUID("324d6ef2-a82c-414d-9001-dc84da1cbea3"),
        )
    assert f"{exc.value}" == expected_error


@pytest.mark.parametrize(
    "downstream_inputs,downstream_required_inputs,upstream_outputs",
    [
        pytest.param(
            {"input_1": _fake_connect_to(1), "input_2": _fake_connect_to(2)},
            ["input_1", "input_2"],
            {"output_1": _fake_output_data(), "output_2": _fake_output_data()},
            id="with_required_inputs_present",
        ),
    ],
)
@pytest.mark.parametrize("user_role", [(UserRole.USER)])
async def test_check_project_node_has_all_required_inputs_ok(
    client: TestClient,
    logged_user: dict[str, Any],
    db_api: ProjectDBAPI,
    inserted_project: dict,
):
    await _check_project_node_has_all_required_inputs(
        client.app,
        db_api,
        user_id=logged_user["id"],
        project_uuid=UUID(inserted_project["uuid"]),
        node_id=UUID("324d6ef2-a82c-414d-9001-dc84da1cbea3"),
    )
