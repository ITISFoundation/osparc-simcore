# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.projects import ProjectID
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_webserver_unit_with_db import MockedStorageSubsystem
from servicelib.aiohttp.long_running_tasks.client import long_running_task_request
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def fake_project(
    fake_project: ProjectDict, workbench_db_column: dict[str, Any]
) -> ProjectDict:
    # OVERRIDES user_project
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    return project


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_clone_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    # mocks backend
    storage_subsystem_mock: MockedStorageSubsystem,
    mock_catalog_service_api_responses: None,
    project_db_cleaner: None,
):
    assert client.app

    project = user_project

    url = client.app.router["clone_project"].url_for(project_id=project["uuid"])
    assert f"/v0/projects/{project['uuid']}:clone" == url.path

    # polls until long-running task is done
    data = None
    async for long_running_task in long_running_task_request(
        client.session, url=client.make_url(url.path), json=None, client_timeout=30
    ):
        print(f"{long_running_task.progress=}")
        if long_running_task.done():
            data = await long_running_task.result()

    assert data is not None
    cloned_project = ProjectGet.parse_obj(data)

    # check whether it's a clone
    assert ProjectID(project["uuid"]) != cloned_project.uuid
    assert project["description"] == cloned_project.description
    assert parse_obj_as(datetime, project["creationDate"]) < parse_obj_as(
        datetime, cloned_project.creation_date
    )

    assert len(project["workbench"]) == len(cloned_project.workbench)
    assert set(project["workbench"].keys()) != set(
        cloned_project.workbench.keys()
    ), "clone does NOT preserve node ids"
