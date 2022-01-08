# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import datetime

import pytest
from aiohttp import web
from simcore_service_webserver._constants import APP_DB_ENGINE_KEY
from simcore_service_webserver.projects.projects_db import (
    ProjectDBAPI,
    _convert_to_db_names,
    _convert_to_schema_names,
)

# FIXTURES


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


def test_convert_to_db_names(fake_schema_dict):
    db_entries = _convert_to_db_names(fake_schema_dict)
    assert "an_entry_that_uses_camel_case" in db_entries
    assert "another_entry_that_uses_camel_case" in db_entries


def test_convert_to_schema_names(fake_db_dict):
    fake_email = "fakey.justafake@fake.faketory"
    db_entries = _convert_to_schema_names(fake_db_dict, fake_email)
    assert "anEntryThatUsesSnakeCase" in db_entries
    assert "anotherEntryThatUsesSnakeCase" in db_entries
    # test date time conversion
    date = datetime.datetime.utcnow()
    fake_db_dict["time_entry"] = date
    db_entries = _convert_to_schema_names(fake_db_dict, fake_email)
    assert "timeEntry" in db_entries
    assert db_entries["timeEntry"] == "{}Z".format(
        date.isoformat(timespec="milliseconds")
    )
    # test conversion of prj owner int to string
    fake_db_dict["prj_owner"] = 1
    db_entries = _convert_to_schema_names(fake_db_dict, fake_email)
    assert "prjOwner" in db_entries
    assert db_entries["prjOwner"] == fake_email


@pytest.fixture
def mock_pg_engine(mocker):
    connection = mocker.AsyncMock(name="Connection")

    mc = mocker.Mock(name="ManagedConnection")
    mc.__aenter__ = mocker.AsyncMock(name="Enter", return_value=connection)
    mc.__aexit__ = mocker.AsyncMock(name="Exit", return_value=False)

    engine = mocker.Mock(name="Engine")
    engine.acquire.return_value = mc
    return engine, connection


# TESTS


async def test_add_projects(fake_project, mock_pg_engine):
    engine, connection = mock_pg_engine

    app = web.Application()
    app[APP_DB_ENGINE_KEY] = engine

    db = ProjectDBAPI(app)
    assert await db.add_projects([fake_project], user_id=-1)

    engine.acquire.assert_called()
    connection.scalar.assert_called()
    connection.execute.assert_called_once()
