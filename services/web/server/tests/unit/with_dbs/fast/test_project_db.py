# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import datetime
import json
import re
from copy import deepcopy
from itertools import combinations
from typing import Any, Dict, List

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
    setup_projects_db,
)
from simcore_service_webserver.users_exceptions import UserNotFoundError
from simcore_service_webserver.utils import to_datetime
from sqlalchemy.engine.result import RowProxy


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


@pytest.mark.parametrize("project_access_rights", [e for e in ProjectAccessRights])
@pytest.mark.parametrize("wanted_permissions", all_permission_combinations())
def test_check_project_permissions(
    user_id: int,
    group_id: int,
    project_access_rights: ProjectAccessRights,
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
    ) -> ProjectAccessRights:
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


def _create_project_db(client: TestClient) -> ProjectDBAPI:
    setup_projects_db(client.app)

    assert APP_PROJECT_DBAPI in client.app
    db_api = client.app[APP_PROJECT_DBAPI]
    assert db_api
    # pylint:disable=protected-access
    assert db_api._app == client.app
    assert db_api._engine
    return db_api


async def test_setup_projects_db(client: TestClient):
    _create_project_db(client)


def test_project_db_engine_creation(postgres_db: sa.engine.Engine):
    db_api = ProjectDBAPI.init_from_engine(postgres_db)
    # pylint:disable=protected-access
    assert db_api._app == {}
    assert db_api._engine == postgres_db


@pytest.fixture()
async def db_api(client: TestClient, postgres_db: sa.engine.Engine) -> ProjectDBAPI:
    db_api = _create_project_db(client)
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
    assert added_prj["creationDate"] == added_prj["lastChangeDate"]
    original_prj.update(exp_overrides)
    for k in _DIFFERENT_KEYS:
        added_prj.pop(k)
        original_prj.pop(k)
    # the rest of the keys shall be the same as the original
    assert added_prj == original_prj


def _assert_project_db_row(
    postgres_db: sa.engine.Engine, project: Dict[str, Any], **kwargs
):
    row: RowProxy = postgres_db.execute(
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
    }
    expected_db_entries.update(kwargs)
    for k in expected_db_entries:
        assert (
            row[k] == expected_db_entries[k]
        ), f"project column [{k}] does not correspond"
    assert row["creation_date"] == to_datetime(project["creationDate"])
    assert row["last_change_date"] == row["creation_date"]
    assert row["last_change_date"] == to_datetime(project["lastChangeDate"])


@pytest.mark.parametrize(
    "user_role",
    [
        # (UserRole.ANONYMOUS),
        # (UserRole.GUEST),
        (UserRole.USER),
        # (UserRole.TESTER),
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
