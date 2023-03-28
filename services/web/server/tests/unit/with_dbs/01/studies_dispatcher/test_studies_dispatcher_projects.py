# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any, AsyncIterator

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import Project, ProjectID
from models_library.projects_nodes_io import NodeID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_login import NewUser
from pytest_simcore.helpers.utils_projects import delete_all_projects
from pytest_simcore.helpers.utils_services import list_fake_file_consumers
from simcore_service_webserver.groups_api import auto_add_user_to_groups
from simcore_service_webserver.projects.projects_api import get_project_for_user
from simcore_service_webserver.studies_dispatcher._projects import (
    UserInfo,
    ViewerInfo,
    _add_new_project,
    _create_project_with_filepicker_and_service,
    _create_project_with_service,
)
from simcore_service_webserver.users_api import get_user

FAKE_FILE_VIEWS = list_fake_file_consumers()


@pytest.fixture
async def user(client: TestClient) -> AsyncIterator[UserInfo]:
    async with NewUser(app=client.app) as user_db:
        try:
            # preparation
            await auto_add_user_to_groups(client.app, user_db["id"])
            user_db = await get_user(client.app, user_db["id"])

            # this part is under test  ---
            user = UserInfo(
                id=user_db["id"],
                name=user_db["name"],
                primary_gid=user_db["primary_gid"],
                email=user_db["email"],
            )

            yield user

        finally:
            # tear-down: delete before user gets deleted
            await delete_all_projects(client.app)


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.fixture
def file_picker_id(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


@pytest.fixture
def viewer_id(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


@pytest.mark.parametrize("only_service", [True, False])
@pytest.mark.parametrize(
    "view", FAKE_FILE_VIEWS, ids=[c["display_name"] for c in FAKE_FILE_VIEWS]
)
async def test_add_new_project_from_model_instance(
    only_service: bool,
    view: dict[str, Any],
    client: TestClient,
    mocker: MockerFixture,
    osparc_product_name: str,
    user: UserInfo,
    project_id: ProjectID,
    file_picker_id: NodeID,
    viewer_id: NodeID,
):
    view["label"] = view.pop("display_name")
    viewer = ViewerInfo(**view)
    assert viewer.dict() == view

    mock_directorv2_api = mocker.patch(
        "simcore_service_webserver.director_v2_api.create_or_update_pipeline",
        return_value=None,
    )

    project: Project

    if only_service:
        project = _create_project_with_service(
            project_id,
            viewer_id,
            owner=user,
            viewer_info=viewer,
        )
    else:
        project = _create_project_with_filepicker_and_service(
            project_id,
            file_picker_id,
            viewer_id,
            owner=user,
            download_link="http://httpbin.org/image/jpeg",
            viewer_info=viewer,
        )

    await _add_new_project(client.app, project, user, product_name=osparc_product_name)

    assert mock_directorv2_api.called

    # internally validates project injected in db
    project_db = await get_project_for_user(
        client.app,
        str(project.uuid),
        user.id,
        include_state=False,
    )
    assert set(project_db["workbench"].keys()) == {
        f"{file_picker_id}",
        f"{viewer_id}",
    }
