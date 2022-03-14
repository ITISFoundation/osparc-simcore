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
from typing import Any, Dict, Iterator, List, Optional, Tuple
from uuid import UUID, uuid5

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from psycopg2.errors import UniqueViolation
from simcore_postgres_database.models.groups import GroupType
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.projects.projects_db import (
    APP_PROJECT_DBAPI,
    DB_EXCLUSIVE_COLUMNS,
    SCHEMA_NON_NULL_KEYS,
    ProjectAccessRights,
    ProjectDBAPI,
    ProjectInvalidRightsError,
    _check_project_permissions,
    _convert_to_db_names,
    _convert_to_schema_names,
    _create_project_access_rights,
    _find_changed_dict_keys,
)
from simcore_service_webserver.users_exceptions import UserNotFoundError
from simcore_service_webserver.utils import to_datetime
from sqlalchemy.engine.result import Row


def test_convert_to_db_names(fake_project: Dict[str, Any]):
    db_entries = _convert_to_db_names(fake_project)
    assert "tags" not in db_entries
    assert "prjOwner" not in db_entries

    # there should be not camelcasing in the keys, except inside the workbench
    assert re.match(r"[A-Z]", json.dumps(list(db_entries.keys()))) is None


def test_convert_to_schema_names(fake_project: Dict[str, Any]):
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


@pytest.mark.parametrize("project_access_rights", [e for e in ProjectAccessRights])
def test_project_access_rights_creation(
    group_id: int, project_access_rights: ProjectAccessRights
):
    git_to_access_rights = _create_project_access_rights(
        group_id, project_access_rights
    )
    assert str(group_id) in git_to_access_rights
    assert git_to_access_rights[str(group_id)] == project_access_rights.value


def all_permission_combinations() -> List[str]:
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
    ) -> Dict[str, bool]:
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
    exp_project: Dict[str, Any],
    added_project: Dict[str, Any],
    exp_overrides: Dict[str, Any],
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


def _assert_project_db_row(
    postgres_db: sa.engine.Engine, project: Dict[str, Any], **kwargs
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
    fake_project: Dict[str, Any],
    postgres_db: sa.engine.Engine,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    db_api: ProjectDBAPI,
):
    original_project = deepcopy(fake_project)
    # add project without user id -> by default creates a template
    new_project = await db_api.add_project(prj=fake_project, user_id=None)

    _assert_added_project(
        original_project,
        new_project,
        exp_overrides={"prjOwner": "not_a_user@unknown.com"},
    )

    _assert_project_db_row(postgres_db, new_project, type="TEMPLATE")
    # adding a project with a fake user id raises
    fake_user_id = 4654654654
    with pytest.raises(UserNotFoundError):
        await db_api.add_project(prj=fake_project, user_id=fake_user_id)
        # adding a project with a fake user but forcing as template should still raise
        await db_api.add_project(
            prj=fake_project, user_id=fake_user_id, force_as_template=True
        )

    # adding a project with a logged user does not raise and creates a STANDARD project
    # since we already have a project with that uuid, it shall be updated
    new_project = await db_api.add_project(prj=fake_project, user_id=logged_user["id"])
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

    # adding a project with a logged user and forcing as template, should create a TEMPLATE project owned by the user
    new_project = await db_api.add_project(
        prj=fake_project, user_id=logged_user["id"], force_as_template=True
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
    # add a project with a uuid that is already present, using force_project_uuid shall raise
    with pytest.raises(UniqueViolation):
        await db_api.add_project(
            prj=fake_project, user_id=logged_user["id"], force_project_uuid=True
        )

    # add a project with a bad uuid that is already present, using force_project_uuid shall raise
    fake_project["uuid"] = "some bad uuid"
    with pytest.raises(ValueError):
        await db_api.add_project(
            prj=fake_project, user_id=logged_user["id"], force_project_uuid=True
        )

    # add a project with a bad uuid that is already present, shall not raise
    new_project = await db_api.add_project(
        prj=fake_project, user_id=logged_user["id"], force_project_uuid=False
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


@pytest.mark.parametrize(
    "dict_a, dict_b, exp_changes",
    [
        pytest.param(
            {"state": "PUBLISHED"},
            {"state": "PUBLISHED"},
            {},
            id="same entry",
        ),
        pytest.param(
            {"state": "PUBLISHED"},
            {"inputs": {"in_1": 1, "in_2": 4}},
            {"inputs": {"in_1": 1, "in_2": 4}},
            id="new entry",
        ),
        pytest.param({"state": "PUBLISHED"}, {}, {}, id="empty patch"),
        pytest.param(
            {"state": "PUBLISHED"},
            {"state": "RUNNING"},
            {"state": "RUNNING"},
            id="patch with new data",
        ),
        pytest.param(
            {"inputs": {"in_1": 1, "in_2": 4}},
            {"inputs": {"in_2": 5}},
            {"inputs": {"in_1": 1, "in_2": 5}},
            id="patch with new nested data",
        ),
        pytest.param(
            {"inputs": {"in_1": 1, "in_2": 4}},
            {"inputs": {"in_1": 1, "in_2": 4, "in_6": "new_entry"}},
            {"inputs": {"in_6": "new_entry"}},
            id="patch with additional nested data",
        ),
        pytest.param(
            {
                "inputs": {
                    "in_1": {"some_file": {"etag": "lkjflsdkjfslkdj"}},
                    "in_2": 4,
                }
            },
            {
                "inputs": {
                    "in_1": {"some_file": {"etag": "newEtag"}},
                    "in_2": 4,
                }
            },
            {
                "inputs": {
                    "in_1": {"some_file": {"etag": "newEtag"}},
                }
            },
            id="patch with 2x nested new data",
        ),
        pytest.param(
            {"remove_entries_in_dict": {"outputs": {"out_1": 123, "out_3": True}}},
            {"remove_entries_in_dict": {"outputs": {}}},
            {"remove_entries_in_dict": {"outputs": {"out_1": 123, "out_3": True}}},
            id="removal of data",
        ),
    ],
)
def test_find_changed_dict_keys(
    dict_a: Dict[str, Any], dict_b: Dict[str, Any], exp_changes: Dict[str, Any]
):
    assert (
        _find_changed_dict_keys(dict_a, dict_b, look_for_removed_keys=False)
        == exp_changes
    )


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.USER),
    ],
)
@pytest.mark.parametrize("number_of_nodes", [1, randint(250, 300)])
async def test_patch_user_project_workbench_concurrently(
    fake_project: Dict[str, Any],
    postgres_db: sa.engine.Engine,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    db_api: ProjectDBAPI,
    number_of_nodes: int,
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
    new_project = await db_api.add_project(prj=fake_project, user_id=logged_user["id"])
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

    patched_projects: Tuple[
        Tuple[Dict[str, Any], Dict[str, Any]]
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
