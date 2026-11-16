# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import datetime
import json
import re
from copy import deepcopy
from typing import Any

import pytest
from models_library.basic_regex import DATE_RE
from simcore_service_webserver import utils
from simcore_service_webserver.projects._projects_repository_legacy import (
    convert_to_db_names,
    convert_to_schema_names,
)
from simcore_service_webserver.projects._projects_repository_legacy_utils import (
    DB_EXCLUSIVE_COLUMNS,
    SCHEMA_NON_NULL_KEYS,
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

    # test date time conversion: every representation of one UTC instant must
    # render in the same Zulu format kept by the API
    instant = datetime.datetime(2026, 5, 4, 12, 30, 15, 123000, tzinfo=datetime.UTC)
    for db_value in (
        instant,  # as read from a `timestamptz` column
        instant.replace(tzinfo=None),  # as stored before the column was `timestamptz`
        instant.astimezone(datetime.timezone(datetime.timedelta(hours=2))),
    ):
        db_entries["creation_date"] = db_value
        schema_entries = convert_to_schema_names(db_entries, fake_project["prjOwner"])
        assert "creationDate" in schema_entries
        assert schema_entries["creationDate"] == "2026-05-04T12:30:15.123Z"


def test_convert_to_schema_names_camel_casing(fake_db_dict):
    fake_email = "fakey.justafake@fake.faketory"
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "anEntryThatUsesSnakeCase" in db_entries
    assert "anotherEntryThatUsesSnakeCase" in db_entries
    # test date time conversion
    instant = datetime.datetime(2026, 5, 4, 12, 30, 15, 123000, tzinfo=datetime.UTC)
    fake_db_dict["time_entry"] = instant
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "timeEntry" in db_entries
    assert db_entries["timeEntry"] == "2026-05-04T12:30:15.123Z"
    # test conversion of prj owner int to string
    fake_db_dict["prj_owner"] = 1
    db_entries = convert_to_schema_names(fake_db_dict, fake_email)
    assert "prjOwner" in db_entries
    assert db_entries["prjOwner"] == fake_email


def test_now_is_bound_to_utc():
    """`now()` feeds inserts into `timestamptz` columns, so it must never be naive."""

    assert utils.now().tzinfo is datetime.UTC


def test_now_str_matches_the_api_datetime_format():
    assert re.fullmatch(DATE_RE, utils.now_str())
