import datetime
import json
from copy import deepcopy
from typing import Any, Dict
from uuid import UUID, uuid4

import pytest
import regex
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_login import LoggedUser
from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_service_webserver.projects.projects_db import (
    APP_PROJECT_DBAPI,
    ProjectDBAPI,
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

    # test date time conversion
    date = datetime.datetime.utcnow()
    db_entries["creation_date"] = date
    schema_entries = _convert_to_schema_names(db_entries, fake_project["prjOwner"])
    assert "creationDate" in schema_entries
    assert schema_entries["creationDate"] == "{}Z".format(
        date.isoformat(timespec="milliseconds")
    )


async def test_setup_projects_db(client: TestClient):
    setup_projects_db(client.app)

    assert APP_PROJECT_DBAPI in client.app
    db_api = client.app[APP_PROJECT_DBAPI]
    assert db_api

    assert db_api._app == client.app
    assert db_api._engine


def test_project_db_engine_creation(client: TestClient):
    ProjectDBAPI.init_from_engine(client.app.get(APP_DB_ENGINE_KEY))
