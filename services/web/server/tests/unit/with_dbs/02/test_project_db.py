# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime
import json
import re
from copy import deepcopy
from itertools import combinations
from random import randint
from secrets import choice
from typing import Any, AsyncIterator, Iterator, Optional, get_args
from uuid import UUID, uuid5

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from psycopg2.errors import UniqueViolation
from pytest_simcore.helpers.utils_dict import copy_from_dict_ex
from pytest_simcore.helpers.utils_login import UserInfoDict, log_client_in
from simcore_postgres_database.models.groups import GroupType
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.projects.project_models import ProjectDict
from simcore_service_webserver.projects.projects_db import (
    APP_PROJECT_DBAPI,
    DB_EXCLUSIVE_COLUMNS,
    SCHEMA_NON_NULL_KEYS,
    Permission,
    ProjectAccessRights,
    ProjectDBAPI,
    ProjectInvalidRightsError,
    _check_project_permissions,
    _convert_to_db_names,
    _convert_to_schema_names,
    _create_project_access_rights,
)
from simcore_service_webserver.projects.projects_exceptions import (
    NodeNotFoundError,
    ProjectNotFoundError,
)
from simcore_service_webserver.users_exceptions import UserNotFoundError
from simcore_service_webserver.utils import to_datetime
from sqlalchemy.engine.result import Row


def test_convert_to_db_names(fake_project: dict[str, Any]):
    db_entries = _convert_to_db_names(fake_project)
    assert "tags" not in db_entries
    assert "prjOwner" not in db_entries

    # there should be not camelcasing in the keys, except inside the workbench
    assert re.match(r"[A-Z]", json.dumps(list(db_entries.keys()))) is None


def test_convert_to_schema_names(fake_project: dict[str, Any]):
    db_entries = _convert_to_db_names(fake_project)

    schema_entries = _convert_to_schema_names(db_entries, fake_project["prjOwner"])
    fake_project.pop("tags")
    expected_project = deepcopy(fake_project)
    expected_project.pop("prjOwner")
    assert schema_entries == expected_project

    # if there is a prj_owner, it should be replaced with the email of the owner
    db_entries["prj_owner"] = 321
    schema_entries = _convert_to_schema_names(db_entries, fake_project["prjOwner"])
    expected_project = deepcopy(fake_project)
    assert schema_entries == expected_project

    # test DB exclusive columns
    for col in DB_EXCLUSIVE_COLUMNS:
        db_entries[col] = "some fake stuff"
    schema_entries = _convert_to_schema_names(db_entries, fake_project["prjOwner"])
    for col in DB_EXCLUSIVE_COLUMNS:
        assert col not in schema_entries

    # test non null keys
    for col in SCHEMA_NON_NULL_KEYS:
        db_entries[col] = None
    schema_entries = _convert_to_schema_names(db_entries, fake_project["prjOwner"])
    for col in SCHEMA_NON_NULL_KEYS:
        assert col is not None

    # test date time conversion
    date = datetime.datetime.utcnow()
    db_entries["creation_date"] = date
    schema_entries = _convert_to_schema_names(db_entries, fake_project["prjOwner"])
    assert "creationDate" in schema_entries
    assert schema_entries["creationDate"] == "{}Z".format(
        date.isoformat(timespec="milliseconds")
    )


@pytest.fixture
def group_id() -> int:
    return 234


@pytest.fixture
def user_id() -> int:
    return 132


@pytest.mark.parametrize("project_access_rights", list(ProjectAccessRights))
def test_project_access_rights_creation(
    group_id: int, project_access_rights: ProjectAccessRights
):
    git_to_access_rights = _create_project_access_rights(
        group_id, project_access_rights
    )
    assert str(group_id) in git_to_access_rights
    assert git_to_access_rights[str(group_id)] == project_access_rights.value


def all_permission_combinations() -> list[str]:
    entries_list = ["read", "write", "delete"]
    temp = []
    for i in range(1, len(entries_list) + 1):
        temp.extend(list(combinations(entries_list, i)))
    res = []
    for el in temp:
        res.append("|".join(el))
    return res


@pytest.mark.parametrize("wanted_permissions", all_permission_combinations())
def test_check_project_permissions(
    user_id: int,
    group_id: int,
    wanted_permissions: str,
):
    project = {"access_rights": {}}

    # this should not raise as needed permissions is empty
    _check_project_permissions(project, user_id, user_groups=[], permission="")

    # this should raise cause we have no user groups defined and we want permission
    with pytest.raises(ProjectInvalidRightsError):
        _check_project_permissions(
            project, user_id, user_groups=[], permission=wanted_permissions
        )

    def _project_access_rights_from_permissions(
        permissions: str, invert: bool = False
    ) -> dict[str, bool]:
        access_rights = {}
        for p in ["read", "write", "delete"]:
            access_rights[p] = (
                p in permissions if invert == False else p not in permissions
            )
        return access_rights

    # primary group has needed access, so this should not raise
    project = {
        "access_rights": {
            str(group_id): _project_access_rights_from_permissions(wanted_permissions)
        }
    }
    user_groups = [
        {"type": GroupType.PRIMARY, "gid": group_id},
        {"type": GroupType.EVERYONE, "gid": 2},
    ]
    _check_project_permissions(project, user_id, user_groups, wanted_permissions)

    # primary group does not have access, it should raise
    project = {
        "access_rights": {
            str(group_id): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            )
        }
    }
    with pytest.raises(ProjectInvalidRightsError):
        _check_project_permissions(project, user_id, user_groups, wanted_permissions)

    # if no primary group, we rely on standard groups and the most permissive access are used. so this should not raise
    project = {
        "access_rights": {
            str(group_id): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
            str(group_id + 1): _project_access_rights_from_permissions(
                wanted_permissions
            ),
            str(group_id + 2): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
        }
    }
    user_groups = [
        {"type": GroupType.PRIMARY, "gid": group_id},
        {"type": GroupType.EVERYONE, "gid": 2},
        {"type": GroupType.STANDARD, "gid": group_id + 1},
        {"type": GroupType.STANDARD, "gid": group_id + 2},
    ]
    _check_project_permissions(project, user_id, user_groups, wanted_permissions)

    # if both primary and standard do not have rights it should raise
    project = {
        "access_rights": {
            str(group_id): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
            str(group_id + 1): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
            str(group_id + 2): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
        }
    }
    user_groups = [
        {"type": GroupType.PRIMARY, "gid": group_id},
        {"type": GroupType.EVERYONE, "gid": 2},
        {"type": GroupType.STANDARD, "gid": group_id + 1},
        {"type": GroupType.STANDARD, "gid": group_id + 2},
    ]
    with pytest.raises(ProjectInvalidRightsError):
        _check_project_permissions(project, user_id, user_groups, wanted_permissions)

    # the everyone group has access so it should not raise
    project = {
        "access_rights": {
            str(2): _project_access_rights_from_permissions(wanted_permissions),
            str(group_id): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
            str(group_id + 1): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
            str(group_id + 2): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
        }
    }

    _check_project_permissions(project, user_id, user_groups, wanted_permissions)


async def test_setup_projects_db(client: TestClient):
    assert client.app
    db_api = client.app[APP_PROJECT_DBAPI]
    assert db_api
    assert isinstance(db_api, ProjectDBAPI)

    assert db_api._app == client.app
    assert db_api.engine


@pytest.fixture()
def db_api(client: TestClient, postgres_db: sa.engine.Engine) -> Iterator[ProjectDBAPI]:
    assert client.app
    db_api = client.app[APP_PROJECT_DBAPI]

    yield db_api

    # clean the projects
    postgres_db.execute("DELETE FROM projects")


def _assert_added_project(
    exp_project: dict[str, Any],
    added_project: dict[str, Any],
    exp_overrides: dict[str, Any],
):
    original_prj = deepcopy(exp_project)
    added_prj = deepcopy(added_project)
    # no user so the project owner has a pre-defined value
    _DIFFERENT_KEYS = ["creationDate", "lastChangeDate"]

    assert all(added_prj[k] != original_prj[k] for k in _DIFFERENT_KEYS)
    assert to_datetime(added_prj["creationDate"]) > to_datetime(
        exp_project["creationDate"]
    )
    assert to_datetime(added_prj["creationDate"]) <= to_datetime(
        added_prj["lastChangeDate"]
    )
    original_prj.update(exp_overrides)
    for k in _DIFFERENT_KEYS:
        added_prj.pop(k)
        original_prj.pop(k)
    # the rest of the keys shall be the same as the original
    assert added_prj == original_prj


def _assert_projects_to_product_db_row(
    postgres_db: sa.engine.Engine, project: dict[str, Any], product_name: str
):
    rows = postgres_db.execute(
        sa.select([projects_to_products]).where(
            projects_to_products.c.project_uuid == f"{project['uuid']}"
        )
    ).fetchall()
    assert rows
    assert len(rows) == 1
    assert rows[0][projects_to_products.c.product_name] == product_name


def _assert_project_db_row(
    postgres_db: sa.engine.Engine, project: dict[str, Any], **kwargs
):
    row: Optional[Row] = postgres_db.execute(
        f"SELECT * FROM projects WHERE \"uuid\"='{project['uuid']}'"
    ).fetchone()

    expected_db_entries = {
        "type": "STANDARD",
        "uuid": project["uuid"],
        "name": project["name"],
        "description": project["description"],
        "thumbnail": project["thumbnail"],
        "prj_owner": None,
        "workbench": project["workbench"],
        "published": False,
        "access_rights": {},
        "dev": project["dev"],
        "classifiers": project["classifiers"],
        "ui": project["ui"],
        "quality": project["quality"],
        "creation_date": to_datetime(project["creationDate"]),
        "last_change_date": to_datetime(project["lastChangeDate"]),
    }
    expected_db_entries.update(kwargs)
    for k in expected_db_entries:
        assert (
            row[k] == expected_db_entries[k]
        ), f"project column [{k}] does not correspond"
    assert row["last_change_date"] >= row["creation_date"]


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.USER),
    ],
)
async def test_add_project_to_db(
    fake_project: dict[str, Any],
    postgres_db: sa.engine.Engine,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    db_api: ProjectDBAPI,
    osparc_product_name: str,
):
    original_project = deepcopy(fake_project)
    # add project without user id -> by default creates a template
    new_project = await db_api.add_project(
        prj=fake_project, user_id=None, product_name=osparc_product_name
    )

    _assert_added_project(
        original_project,
        new_project,
        exp_overrides={"prjOwner": "not_a_user@unknown.com"},
    )
    _assert_project_db_row(postgres_db, new_project, type="TEMPLATE")
    _assert_projects_to_product_db_row(postgres_db, new_project, osparc_product_name)
    # adding a project with a fake user id raises
    fake_user_id = 4654654654
    with pytest.raises(UserNotFoundError):
        await db_api.add_project(
            prj=fake_project, user_id=fake_user_id, product_name=osparc_product_name
        )
        # adding a project with a fake user but forcing as template should still raise
        await db_api.add_project(
            prj=fake_project,
            user_id=fake_user_id,
            force_as_template=True,
            product_name=osparc_product_name,
        )

    # adding a project with a logged user does not raise and creates a STANDARD project
    # since we already have a project with that uuid, it shall be updated
    new_project = await db_api.add_project(
        prj=fake_project, user_id=logged_user["id"], product_name=osparc_product_name
    )
    assert new_project["uuid"] != original_project["uuid"]
    _assert_added_project(
        original_project,
        new_project,
        exp_overrides={
            "uuid": new_project["uuid"],
            "prjOwner": logged_user["email"],
            "accessRights": {
                str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
            },
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
    )
    _assert_projects_to_product_db_row(postgres_db, new_project, osparc_product_name)

    # adding a project with a logged user and forcing as template, should create a TEMPLATE project owned by the user
    new_project = await db_api.add_project(
        prj=fake_project,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        force_as_template=True,
    )
    assert new_project["uuid"] != original_project["uuid"]
    _assert_added_project(
        original_project,
        new_project,
        exp_overrides={
            "uuid": new_project["uuid"],
            "prjOwner": logged_user["email"],
            "accessRights": {
                str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
            },
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
        type="TEMPLATE",
    )
    _assert_projects_to_product_db_row(postgres_db, new_project, osparc_product_name)
    # add a project with a uuid that is already present, using force_project_uuid shall raise
    with pytest.raises(UniqueViolation):
        await db_api.add_project(
            prj=fake_project,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            force_project_uuid=True,
        )

    # add a project with a bad uuid that is already present, using force_project_uuid shall raise
    fake_project["uuid"] = "some bad uuid"
    with pytest.raises(ValueError):
        await db_api.add_project(
            prj=fake_project,
            user_id=logged_user["id"],
            product_name=osparc_product_name,
            force_project_uuid=True,
        )

    # add a project with a bad uuid that is already present, shall not raise
    new_project = await db_api.add_project(
        prj=fake_project,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        force_project_uuid=False,
    )
    _assert_added_project(
        original_project,
        new_project,
        exp_overrides={
            "uuid": new_project["uuid"],
            "prjOwner": logged_user["email"],
            "accessRights": {
                str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
            },
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
    )
    _assert_projects_to_product_db_row(postgres_db, new_project, osparc_product_name)


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
        await db_api.patch_user_project_workbench(
            partial_workbench_data,
            logged_user["id"],
            fake_project["uuid"],
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
    osparc_product_name: str,
):
    empty_fake_project = deepcopy(fake_project)
    workbench = empty_fake_project.setdefault("workbench", {})
    assert isinstance(workbench, dict)
    workbench.clear()

    new_project = await db_api.add_project(
        prj=empty_fake_project,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    partial_workbench_data = {
        faker.uuid4(): {
            "key": f"simcore/services/comp/{faker.pystr()}",
            "version": faker.numerify("%.#.#"),
            "label": faker.text(),
        }
        for _ in range(faker.pyint(min_value=5, max_value=30))
    }
    patched_project, changed_entries = await db_api.patch_user_project_workbench(
        partial_workbench_data,
        logged_user["id"],
        new_project["uuid"],
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
    osparc_product_name: str,
):
    empty_fake_project = deepcopy(fake_project)
    workbench = empty_fake_project.setdefault("workbench", {})
    assert isinstance(workbench, dict)
    workbench.clear()

    new_project = await db_api.add_project(
        prj=empty_fake_project,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
    )
    partial_workbench_data = {
        faker.uuid4(): {
            "version": faker.numerify("%.#.#"),
            "label": faker.text(),
        }
        for _ in range(faker.pyint(min_value=5, max_value=30))
    }
    with pytest.raises(NodeNotFoundError):
        await db_api.patch_user_project_workbench(
            partial_workbench_data,
            logged_user["id"],
            new_project["uuid"],
        )


@pytest.mark.parametrize(
    "user_role",
    [(UserRole.USER)],
)
@pytest.mark.parametrize("number_of_nodes", [1, randint(250, 300)])
async def test_patch_user_project_workbench_concurrently(
    fake_project: dict[str, Any],
    postgres_db: sa.engine.Engine,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    db_api: ProjectDBAPI,
    number_of_nodes: int,
    osparc_product_name: str,
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
    new_project = await db_api.add_project(
        prj=fake_project, user_id=logged_user["id"], product_name=osparc_product_name
    )
    _assert_added_project(
        original_project,
        new_project,
        exp_overrides={
            "prjOwner": logged_user["email"],
            "accessRights": {
                str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
            },
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
    )

    # patch all the nodes concurrently
    randomly_created_outputs = [
        {"outputs": {f"out_{k}": f"{k}"} for k in range(randint(1, 10))}
        for n in range(_NUMBER_OF_NODES)
    ]
    for n in range(_NUMBER_OF_NODES):
        expected_project["workbench"][node_uuids[n]].update(randomly_created_outputs[n])

    patched_projects: list[
        tuple[dict[str, Any], dict[str, Any]]
    ] = await asyncio.gather(
        *[
            db_api.patch_user_project_workbench(
                {node_uuids[n]: randomly_created_outputs[n]},
                logged_user["id"],
                new_project["uuid"],
            )
            for n in range(_NUMBER_OF_NODES)
        ]
    )
    # NOTE: each returned project contains the project with some updated workbenches
    # the ordering is uncontrolled.
    # The important thing is that the final result shall contain ALL the changes

    for (prj, changed_entries), node_uuid, exp_outputs in zip(
        patched_projects, node_uuids, randomly_created_outputs
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
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )

    # now concurrently remove the outputs
    for n in range(_NUMBER_OF_NODES):
        expected_project["workbench"][node_uuids[n]]["outputs"] = {}

    patched_projects = await asyncio.gather(
        *[
            db_api.patch_user_project_workbench(
                {node_uuids[n]: {"outputs": {}}},
                logged_user["id"],
                new_project["uuid"],
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
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )

    # now concurrently remove the outputs
    for n in range(_NUMBER_OF_NODES):
        expected_project["workbench"][node_uuids[n]]["outputs"] = {}

    patched_projects = await asyncio.gather(
        *[
            db_api.patch_user_project_workbench(
                {node_uuids[n]: {"outputs": {}}},
                logged_user["id"],
                new_project["uuid"],
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
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )


@pytest.fixture()
async def lots_of_projects_and_nodes(
    logged_user: dict[str, Any],
    fake_project: dict[str, Any],
    db_api: ProjectDBAPI,
    osparc_product_name: str,
) -> AsyncIterator[dict[ProjectID, list[NodeID]]]:
    """Will create >1000 projects with each between 200-1434 nodes"""
    NUMBER_OF_PROJECTS = 1245

    BASE_UUID = UUID("ccc0839f-93b8-4387-ab16-197281060927")
    all_created_projects = {}
    project_creation_tasks = []
    for p in range(NUMBER_OF_PROJECTS):
        project_uuid = uuid5(BASE_UUID, f"project_{p}")
        all_created_projects[project_uuid] = []
        workbench = {}
        for n in range(randint(200, 1434)):
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
            db_api.add_project(
                prj=new_project,
                user_id=logged_user["id"],
                product_name=osparc_product_name,
            )
        )
    await asyncio.gather(*project_creation_tasks)
    print(f"---> created {len(all_created_projects)} projects in the database")
    yield all_created_projects
    print(f"<--- removed {len(all_created_projects)} projects in the database")

    # cleanup
    await asyncio.gather(
        *[
            db_api.delete_user_project(logged_user["id"], f"{p_uuid}")
            for p_uuid in all_created_projects
        ]
    )


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_node_id_exists(
    db_api: ProjectDBAPI, lots_of_projects_and_nodes: dict[ProjectID, list[NodeID]]
):

    # create a node uuid that does not exist from an existing project
    existing_project_id = choice(list(lots_of_projects_and_nodes.keys()))
    not_existing_node_id_in_existing_project = uuid5(
        existing_project_id, "node_invalid_node"
    )

    node_id_exists = await db_api.node_id_exists(
        f"{not_existing_node_id_in_existing_project}"
    )
    assert node_id_exists == False
    existing_node_id = choice(lots_of_projects_and_nodes[existing_project_id])
    node_id_exists = await db_api.node_id_exists(f"{existing_node_id}")
    assert node_id_exists == True


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_get_node_ids_from_project(
    db_api: ProjectDBAPI, lots_of_projects_and_nodes: dict[ProjectID, list[NodeID]]
):
    for project_id in lots_of_projects_and_nodes:
        node_ids_inside_project: set[str] = await db_api.get_node_ids_from_project(
            f"{project_id}"
        )
        assert node_ids_inside_project == {
            f"{n}" for n in lots_of_projects_and_nodes[project_id]
        }


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
):
    PROJECT_DICT_IGNORE_FIELDS = {"lastChangeDate"}
    original_project = user_project
    # replace the project with the same should do nothing
    working_project = await db_api.replace_user_project(
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
    replaced_project = await db_api.replace_user_project(
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

    # the frontend sends project without some fields, but for FRONTEND type of nodes
    # replacing should keep the values
    FRONTEND_EXCLUDED_FIELDS = ["outputs", "progress", "runHash"]
    incoming_frontend_project = deepcopy(original_project)
    for node_data in incoming_frontend_project["workbench"].values():
        if "frontend" not in node_data["key"]:
            for field in FRONTEND_EXCLUDED_FIELDS:
                node_data.pop(field, None)
    replaced_project = await db_api.replace_user_project(
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
    osparc_product_name: str,
    access_rights: dict[str, bool],
    user_role: UserRole,
    client: TestClient,
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

    await db_api.add_project(
        prj=new_project,
        user_id=owner_id,
        product_name=osparc_product_name,
    )

    for permission in get_args(Permission):
        assert permission in access_rights

        # owner always is allowed to do everything
        assert await db_api.has_permission(owner_id, project_id, permission) is True

        # user does not exits
        assert await db_api.has_permission(-1, project_id, permission) is False

        # other user
        assert (
            await db_api.has_permission(second_user["id"], project_id, permission)
            is access_rights[permission]
        ), f"Found unexpected {permission=} for {access_rights=} of {user_role=} and {project_id=}"
