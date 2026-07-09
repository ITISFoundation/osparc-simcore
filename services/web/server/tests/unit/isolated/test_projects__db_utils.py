# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import datetime
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest
from faker import Faker
from models_library.groups import GroupID
from simcore_service_webserver.projects._projects_repository_legacy import (
    ProjectAccessRights,
    convert_to_db_names,
    convert_to_schema_names,
    create_project_access_rights,
)
from simcore_service_webserver.projects._projects_repository_legacy_utils import (
    DB_EXCLUSIVE_COLUMNS,
    SCHEMA_NON_NULL_KEYS,
    assemble_array_groups,
)


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
    date = datetime.datetime.now(datetime.UTC)
    db_entries["creation_date"] = date
    schema_entries = convert_to_schema_names(db_entries, fake_project["prjOwner"])
    assert "creationDate" in schema_entries
    assert schema_entries["creationDate"] == "{}Z".format(date.isoformat(timespec="milliseconds"))


def test_convert_to_schema_names_camel_casing(fake_db_dict):
    fake_email = "fakey.justafake@fake.faketory"
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "anEntryThatUsesSnakeCase" in db_entries
    assert "anotherEntryThatUsesSnakeCase" in db_entries
    # test date time conversion
    date = datetime.datetime.now(datetime.UTC)
    fake_db_dict["time_entry"] = date
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "timeEntry" in db_entries
    assert db_entries["timeEntry"] == "{}Z".format(date.isoformat(timespec="milliseconds"))
    # test conversion of prj owner int to string
    fake_db_dict["prj_owner"] = 1
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "prjOwner" in db_entries
    assert db_entries["prjOwner"] == fake_email


@pytest.fixture
def group_id(faker: Faker) -> GroupID:
    return faker.pyint(min_value=1)


@pytest.mark.parametrize("project_access_rights", ProjectAccessRights.all())
def test_project_access_rights_creation(group_id: int, project_access_rights: ProjectAccessRights):
    git_to_access_rights = create_project_access_rights(group_id, project_access_rights)
    assert str(group_id) in git_to_access_rights
    assert git_to_access_rights[str(group_id)] == project_access_rights.value


def test_assemble_array_groups_empty_user_groups():
    assert assemble_array_groups([]) == "array[]::text[]"


@dataclass
class FakeUserGroup:
    gid: int


def test_assemble_array_groups():
    fake_user_groups = [FakeUserGroup(gid=n) for n in range(5)]
    assert assemble_array_groups(fake_user_groups) == "array['0', '1', '2', '3', '4']"  # type: ignore
