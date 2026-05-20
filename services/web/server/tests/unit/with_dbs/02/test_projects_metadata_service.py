# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from faker import Faker
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.webserver_projects import NewProject
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.projects._metadata_service import (
    batch_get_project_custom_metadata_for_user,
    set_project_custom_metadata,
)
from simcore_service_webserver.projects.exceptions import (
    ProjectInvalidRightsError,
    ProjectNotFoundError,
)
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
async def second_project(
    client: TestClient,
    logged_user: UserInfoDict,
    tests_data_dir: Path,
    osparc_product_name: ProductName,
    fake_project: ProjectDict,
) -> ProjectDict:
    assert client.app
    async with NewProject(
        {**fake_project, "uuid": None},
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as project:
        yield project


async def test_batch_get_project_custom_metadata_for_user_empty_list(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    assert client.app
    result = await batch_get_project_custom_metadata_for_user(
        client.app,
        user_id=logged_user["id"],
        project_uuids=[],
    )
    assert result == {}


async def test_batch_get_project_custom_metadata_for_user_single_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    assert client.app
    user_id = logged_user["id"]
    project_uuid = ProjectID(user_project["uuid"])

    custom = {"key": "value", "number": 42}
    await set_project_custom_metadata(client.app, user_id, project_uuid, custom)

    result = await batch_get_project_custom_metadata_for_user(
        client.app,
        user_id=user_id,
        project_uuids=[project_uuid],
    )
    assert result == {project_uuid: custom}


async def test_batch_get_project_custom_metadata_for_user_multiple_projects(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    second_project: ProjectDict,
):
    assert client.app
    user_id = logged_user["id"]
    project_uuid_1 = ProjectID(user_project["uuid"])
    project_uuid_2 = ProjectID(second_project["uuid"])

    custom_1 = {"label": "first", "x": 1}
    custom_2 = {"label": "second", "x": 2}
    await set_project_custom_metadata(client.app, user_id, project_uuid_1, custom_1)
    await set_project_custom_metadata(client.app, user_id, project_uuid_2, custom_2)

    result = await batch_get_project_custom_metadata_for_user(
        client.app,
        user_id=user_id,
        project_uuids=[project_uuid_1, project_uuid_2],
    )
    assert result == {project_uuid_1: custom_1, project_uuid_2: custom_2}


async def test_batch_get_project_custom_metadata_for_user_no_metadata_returns_empty_dicts(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    second_project: ProjectDict,
):
    assert client.app
    user_id = logged_user["id"]
    project_uuid_1 = ProjectID(user_project["uuid"])
    project_uuid_2 = ProjectID(second_project["uuid"])

    result = await batch_get_project_custom_metadata_for_user(
        client.app,
        user_id=user_id,
        project_uuids=[project_uuid_1, project_uuid_2],
    )
    assert result == {project_uuid_1: {}, project_uuid_2: {}}


async def test_batch_get_project_custom_metadata_for_user_not_owned_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
):
    assert client.app
    other_user_id = UserID(faker.pyint(min_value=9000, max_value=99999))
    project_uuid = ProjectID(user_project["uuid"])

    with pytest.raises(ProjectInvalidRightsError):
        await batch_get_project_custom_metadata_for_user(
            client.app,
            user_id=other_user_id,
            project_uuids=[project_uuid],
        )


async def test_batch_get_project_custom_metadata_for_user_nonexistent_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    faker: Faker,
):
    assert client.app
    user_id = logged_user["id"]
    nonexistent_uuid = ProjectID(faker.uuid4())

    with pytest.raises(ProjectNotFoundError):
        await batch_get_project_custom_metadata_for_user(
            client.app,
            user_id=user_id,
            project_uuids=[nonexistent_uuid],
        )
