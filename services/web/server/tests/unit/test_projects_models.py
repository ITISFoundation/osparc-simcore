# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import datetime
from asyncio import Future
from unittest.mock import MagicMock

import pytest

from simcore_service_webserver.projects.projects_db import (
    ProjectDBAPI,
    _convert_to_db_names,
    _convert_to_schema_names,
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


def test_convert_to_db_names(fake_schema_dict):
    db_entries = _convert_to_db_names(fake_schema_dict)
    assert "an_entry_that_uses_camel_case" in db_entries
    assert "another_entry_that_uses_camel_case" in db_entries


def test_convert_to_schema_names(fake_db_dict):
    db_entries = _convert_to_schema_names(fake_db_dict)
    assert "anEntryThatUsesSnakeCase" in db_entries
    assert "anotherEntryThatUsesSnakeCase" in db_entries
    # test date time conversion
    date = datetime.datetime.utcnow()
    fake_db_dict["time_entry"] = date
    db_entries = _convert_to_schema_names(fake_db_dict)
    assert "timeEntry" in db_entries
    assert db_entries["timeEntry"] == "{}Z".format(
        date.isoformat(timespec="milliseconds")
    )


@pytest.fixture
def user_id():
    return -1


class MockAsyncContextManager(MagicMock):
    mock_object = None

    async def __aenter__(self):
        return self.mock_object

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_db_engine(mocker):
    def create_engine(mock_result):
        mock_connection = mocker.patch("aiopg.sa.SAConnection", spec=True)
        mock_connection.execute.return_value = Future()
        mock_connection.execute.return_value.set_result(mock_result)

        mock_context_manager = MockAsyncContextManager()
        mock_context_manager.mock_object = mock_connection

        mock_db_engine = mocker.patch("aiopg.sa.engine.Engine", spec=True)
        mock_db_engine.acquire.return_value = mock_context_manager
        return mock_db_engine, mock_connection

    yield create_engine


async def test_add_projects(fake_project, user_id, mocker, mock_db_engine):

    mock_result_row = mocker.patch("aiopg.sa.result.RowProxy", spec=True)

    mock_result = mocker.patch("aiopg.sa.result.ResultProxy", spec=True)
    mock_result.first.return_value = Future()
    mock_result.first.return_value.set_result(mock_result_row)

    db_engine, mock_connection = mock_db_engine(mock_result)

    db = ProjectDBAPI.init_from_engine(db_engine)
    await db.add_projects([fake_project], user_id=user_id)

    db_engine.acquire.assert_called()
    mock_connection.execute.assert_called()
    assert mock_connection.execute.call_count == 3


# not sure this is useful...
# async def test_load_projects(user_id, mocker, mock_db_engine):
#     mock_result_row = mocker.patch("aiopg.sa.result.RowProxy", spec=True)

#     mock_result = mocker.patch("aiopg.sa.result.ResultProxy", spec=True)
#     mock_result.fetchone.return_value = Future()
#     mock_result.fetchone.return_value.set_result(mock_result_row)

#     db_engine, mock_connection = mock_db_engine(mock_result)

#     projects = await ProjectDB.load_user_projects(user_id=user_id, db_engine=db_engine)

#     db_engine.acquire.assert_called()
#     mock_connection.execute.assert_called()
#     assert mock_connection.execute.call_count == 2

# async def test_get_project():
#     pass

# async def test_update_project():
#     pass

# async def test_delete_project():
#     pass
