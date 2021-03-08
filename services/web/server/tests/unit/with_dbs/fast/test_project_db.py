import datetime
import json
from typing import Any, Dict
from uuid import UUID, uuid4

import pytest
import regex
from aiohttp.test_utils import TestClient
from models_library.projects import ProjectAtDB
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver.projects.projects_db import (
    APP_PROJECT_DBAPI,
    _convert_to_db_names,
    _convert_to_schema_names,
    setup_projects_db,
)
from simcore_service_webserver.security_roles import UserRole


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


@pytest.fixture
async def logged_user(client, user_role: UserRole):
    """adds a user in db and logs in with client

    NOTE: role fixture is defined as a parametrization below
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        yield user


def test_convert_to_db_names(fake_project: Dict[str, Any]):
    db_entries = _convert_to_db_names(fake_project)
    assert "tags" not in db_entries
    assert "prjOwner" not in db_entries

    # there should be not camelcasing in the keys, except inside the workbench
    assert regex.match(r"[A-Z]", json.dumps(list(db_entries.keys()))) is None


def test_convert_to_schema_names(fake_db_dict: Dict[str, Any]):
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


async def test_setup_projects_db(client: TestClient):
    setup_projects_db(client.app)

    assert APP_PROJECT_DBAPI in client.app
    assert client.app[APP_PROJECT_DBAPI]
