# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import sys
import uuid
from pathlib import Path
from typing import Dict

import pytest

from pytest_simcore.helpers.utils_login import LoggedUser
from pytest_simcore.helpers.utils_projects import NewProject
from simcore_service_webserver.security_roles import UserRole

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def mock_workbench_payload():
    file_path = current_dir / "workbench_sleeper_payload.json"
    with file_path.open() as fp:
        return json.load(fp)


@pytest.fixture(scope="session")
def mock_project(fake_data_dir, mock_workbench_payload):
    with (fake_data_dir / "fake-project.json").open() as fp:
        project = json.load(fp)
    project["workbench"] = mock_workbench_payload["workbench"]
    return project


@pytest.fixture
async def logged_user(client, user_role: UserRole) -> Dict:
    """adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        yield user


@pytest.fixture
async def user_project(client, mock_project, logged_user) -> Dict:
    mock_project["prjOwner"] = logged_user["name"]

    async with NewProject(
        mock_project, client.app, user_id=logged_user["id"]
    ) as project:
        yield project


@pytest.fixture
def project_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
def node_uuid() -> str:
    return "some_node_id"


@pytest.fixture(scope="session")
def user_id() -> str:
    return "some_id"
