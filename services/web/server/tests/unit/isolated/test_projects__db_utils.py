import datetime
import json
import re
from copy import deepcopy
from itertools import combinations
from typing import Any

import pytest
from simcore_postgres_database.models.groups import GroupType
from simcore_service_webserver.projects._db_utils import (
    DB_EXCLUSIVE_COLUMNS,
    SCHEMA_NON_NULL_KEYS,
)
from simcore_service_webserver.projects.db import (
    ANY_USER,
    check_project_permissions,
    convert_to_db_names,
    convert_to_schema_names,
)
from simcore_service_webserver.projects.exceptions import ProjectInvalidRightsError


@pytest.fixture
def fake_schema_dict():
    return {
        "anEntryThatUsesCamelCase": "I'm the entry",
        "anotherEntryThatUsesCamelCase": "I'm also an entry",
    }


@pytest.fixture
def fake_db_dict():
    return {
        "an_entry_that_uses_snake_case": "I'm the entry",
        "another_entry_that_uses_snake_case": "I'm also an entry",
    }


def test_convert_to_db_names_transform_casing(fake_schema_dict):
    db_entries = convert_to_db_names(fake_schema_dict)
    assert "an_entry_that_uses_camel_case" in db_entries
    assert "another_entry_that_uses_camel_case" in db_entries


def test_convert_to_db_names(fake_project: dict[str, Any]):
    db_entries = convert_to_db_names(fake_project)
    assert "tags" not in db_entries
    assert "prjOwner" not in db_entries

    # there should be not camelcasing in the keys, except inside the workbench
    assert re.match(r"[A-Z]", json.dumps(list(db_entries.keys()))) is None


def test_convert_to_schema_names(fake_project: dict[str, Any]):
    db_entries = convert_to_db_names(fake_project)

    schema_entries = convert_to_schema_names(db_entries, fake_project["prjOwner"])
    fake_project.pop("tags")
    expected_project = deepcopy(fake_project)
    expected_project.pop("prjOwner")
    assert schema_entries == expected_project

    # if there is a prj_owner, it should be replaced with the email of the owner
    db_entries["prj_owner"] = 321
    schema_entries = convert_to_schema_names(db_entries, fake_project["prjOwner"])
    expected_project = deepcopy(fake_project)
    assert schema_entries == expected_project

    # test DB exclusive columns
    for col in DB_EXCLUSIVE_COLUMNS:
        db_entries[col] = "some fake stuff"
    schema_entries = convert_to_schema_names(db_entries, fake_project["prjOwner"])
    for col in DB_EXCLUSIVE_COLUMNS:
        assert col not in schema_entries

    # test non null keys
    for col in SCHEMA_NON_NULL_KEYS:
        db_entries[col] = None
    schema_entries = convert_to_schema_names(db_entries, fake_project["prjOwner"])
    for col in SCHEMA_NON_NULL_KEYS:
        assert col is not None

    # test date time conversion
    date = datetime.datetime.utcnow()
    db_entries["creation_date"] = date
    schema_entries = convert_to_schema_names(db_entries, fake_project["prjOwner"])
    assert "creationDate" in schema_entries
    assert schema_entries["creationDate"] == "{}Z".format(
        date.isoformat(timespec="milliseconds")
    )


def test_convert_to_schema_names_camel_casing(fake_db_dict):
    fake_email = "fakey.justafake@fake.faketory"
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "anEntryThatUsesSnakeCase" in db_entries
    assert "anotherEntryThatUsesSnakeCase" in db_entries
    # test date time conversion
    date = datetime.datetime.utcnow()
    fake_db_dict["time_entry"] = date
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "timeEntry" in db_entries
    assert db_entries["timeEntry"] == "{}Z".format(
        date.isoformat(timespec="milliseconds")
    )
    # test conversion of prj owner int to string
    fake_db_dict["prj_owner"] = 1
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "prjOwner" in db_entries
    assert db_entries["prjOwner"] == fake_email


def test_check_project_permissions_for_any_user():
    project = {"access_rights": {"1": {"read": True, "write": False, "delete": False}}}

    check_project_permissions(
        project,
        user_id=ANY_USER,
        user_groups=[{"gid": 1, "type": GroupType.EVERYONE}],
        permission="read",
    )


def all_permission_combinations() -> list[str]:
    entries_list = ["read", "write", "delete"]
    temp = []
    for i in range(1, len(entries_list) + 1):
        temp.extend(list(combinations(entries_list, i)))
    return ["|".join(el) for el in temp]


@pytest.mark.parametrize("wanted_permissions", all_permission_combinations())
def test_check_project_permissions(
    user_id: int,
    group_id: int,
    wanted_permissions: str,
):
    project = {"access_rights": {}}

    # this should not raise as needed permissions is empty
    check_project_permissions(project, user_id, user_groups=[], permission="")

    # this should raise cause we have no user groups defined and we want permission
    with pytest.raises(ProjectInvalidRightsError):
        check_project_permissions(
            project, user_id, user_groups=[], permission=wanted_permissions
        )

    def _project_access_rights_from_permissions(
        permissions: str, *, invert: bool
    ) -> dict[str, bool]:
        access_rights = {}
        for p in ["read", "write", "delete"]:
            access_rights[p] = (
                p in permissions if invert is False else p not in permissions
            )
        return access_rights

    # primary group has needed access, so this should not raise
    project = {
        "access_rights": {
            str(group_id): _project_access_rights_from_permissions(
                wanted_permissions, invert=False
            )
        }
    }
    user_groups = [
        {"type": GroupType.PRIMARY, "gid": group_id},
        {"type": GroupType.EVERYONE, "gid": 2},
    ]
    check_project_permissions(project, user_id, user_groups, wanted_permissions)

    # primary group does not have access, it should raise
    project = {
        "access_rights": {
            str(group_id): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            )
        }
    }
    with pytest.raises(ProjectInvalidRightsError):
        check_project_permissions(project, user_id, user_groups, wanted_permissions)

    # if no primary group, we rely on standard groups and the most permissive access are used. so this should not raise
    project = {
        "access_rights": {
            str(group_id): _project_access_rights_from_permissions(
                wanted_permissions, invert=True
            ),
            str(group_id + 1): _project_access_rights_from_permissions(
                wanted_permissions, invert=False
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
    check_project_permissions(project, user_id, user_groups, wanted_permissions)

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
        check_project_permissions(project, user_id, user_groups, wanted_permissions)

    # the everyone group has access so it should not raise
    project = {
        "access_rights": {
            str(2): _project_access_rights_from_permissions(
                wanted_permissions, invert=False
            ),
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

    check_project_permissions(project, user_id, user_groups, wanted_permissions)
