# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Awaitable, Callable
from uuid import UUID

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects import Project, ProjectID
from models_library.rest_pagination import Page
from models_library.users import UserID
from pydantic.main import BaseModel
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver._meta import API_VTAG as VX
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.version_control.models import (
    CheckpointApiModel,
    RepoApiModel,
)


async def assert_resp_page(
    resp: aiohttp.ClientResponse,
    expected_page_cls: type[Page],
    expected_total: int,
    expected_count: int,
):
    assert resp.status == web.HTTPOk.status_code, f"Got {await resp.text()}"
    body = await resp.json()

    page = expected_page_cls.parse_obj(body)
    assert page.meta.total == expected_total
    assert page.meta.count == expected_count
    return page


async def assert_status_and_body(
    resp, expected_cls: type[web.HTTPException], expected_model: type[BaseModel]
) -> BaseModel:
    data, _ = await assert_status(resp, expected_cls)
    return expected_model.parse_obj(data)


@pytest.mark.acceptance_test()
async def test_workflow(
    client: TestClient,
    user_project: ProjectDict,
    request_update_project: Callable[[TestClient, UUID], Awaitable],
    director_v2_service_mock: None,
):
    # pylint: disable=too-many-statements

    project_uuid = user_project["uuid"]

    # get existing project
    resp = await client.get(f"/{VX}/projects/{project_uuid}")
    data, _ = await assert_status(resp, web.HTTPOk)
    project = Project.parse_obj(data)
    assert project.uuid == UUID(project_uuid)

    #
    # list repos i.e. versioned projects
    resp = await client.get(f"/{VX}/repos/projects")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == []

    #
    # CREATE a checkpoint
    resp = await client.post(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints",
        json={"tag": "v1", "message": "init"},
    )
    data, _ = await assert_status(resp, web.HTTPCreated)

    assert data
    checkpoint1 = CheckpointApiModel.parse_obj(data)  # NOTE: this is NOT API model

    #
    # this project now has a repo
    resp = await client.get(f"/{VX}/repos/projects")
    page = await assert_resp_page(
        resp, expected_page_cls=Page[ProjectDict], expected_total=1, expected_count=1
    )

    repo = RepoApiModel.parse_obj(page.data[0])
    assert repo.project_uuid == UUID(project_uuid)

    # GET checkpoint with HEAD
    resp = await client.get(f"/{VX}/repos/projects/{project_uuid}/checkpoints/HEAD")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert CheckpointApiModel.parse_obj(data) == checkpoint1

    # TODO: GET checkpoint with tag
    with pytest.raises(aiohttp.ClientResponseError) as excinfo:
        resp = await client.get(f"/{VX}/repos/projects/{project_uuid}/checkpoints/v1")
        resp.raise_for_status()

    assert CheckpointApiModel.parse_obj(data) == checkpoint1

    assert excinfo.value.status == web.HTTPNotImplemented.status_code

    # GET checkpoint with id
    resp = await client.get(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints/{checkpoint1.id}"
    )
    assert str(resp.url) == checkpoint1.url
    assert CheckpointApiModel.parse_obj(data) == checkpoint1

    # LIST checkpoints
    resp = await client.get(f"/{VX}/repos/projects/{project_uuid}/checkpoints")
    page = await assert_resp_page(
        resp,
        expected_page_cls=Page[CheckpointApiModel],
        expected_total=1,
        expected_count=1,
    )

    assert CheckpointApiModel.parse_obj(page.data[0]) == checkpoint1

    # UPDATE checkpoint annotations
    resp = await client.patch(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints/{checkpoint1.id}",
        json={"message": "updated message", "tag": "Version 1"},
    )
    data, _ = await assert_status(resp, web.HTTPOk)
    checkpoint1_updated = CheckpointApiModel.parse_obj(data)

    assert checkpoint1.id == checkpoint1_updated.id
    assert checkpoint1.checksum == checkpoint1_updated.checksum
    assert checkpoint1_updated.tags == ("Version 1",)
    assert checkpoint1_updated.message == "updated message"

    # GET view
    resp = await client.get(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints/HEAD/workbench/view"
    )
    data, _ = await assert_status(resp, web.HTTPOk)
    assert (
        data["workbench"]
        == project.dict(exclude_none=True, exclude_unset=True)["workbench"]
    )

    # do some changes in project
    await request_update_project(client, project.uuid)

    # CREATE new checkpoint
    resp = await client.post(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints",
        json={"tag": "v2", "message": "new commit"},
    )
    data, _ = await assert_status(resp, web.HTTPCreated)
    checkpoint2 = CheckpointApiModel.parse_obj(data)
    assert checkpoint2.tags == ("v2",)

    # GET checkpoint with HEAD
    resp = await client.get(f"/{VX}/repos/projects/{project_uuid}/checkpoints/HEAD")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert CheckpointApiModel.parse_obj(data) == checkpoint2

    # CHECKOUT
    resp = await client.post(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints/{checkpoint1.id}:checkout"
    )
    data, _ = await assert_status(resp, web.HTTPOk)
    assert CheckpointApiModel.parse_obj(data) == checkpoint1_updated

    # GET checkpoint with HEAD
    resp = await client.get(f"/{VX}/repos/projects/{project_uuid}/checkpoints/HEAD")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert CheckpointApiModel.parse_obj(data) == checkpoint1_updated

    # get working copy
    resp = await client.get(f"/{VX}/projects/{project_uuid}")
    data, _ = await assert_status(resp, web.HTTPOk)
    project_wc = Project.parse_obj(data)
    assert project_wc.uuid == UUID(project_uuid)
    assert project_wc != project


async def test_create_checkpoint_without_changes(
    client: TestClient, project_uuid: UUID
):
    # CREATE a checkpoint
    resp = await client.post(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints",
        json={"tag": "v1", "message": "first commit"},
    )
    data, _ = await assert_status(resp, web.HTTPCreated)

    assert data
    checkpoint1 = CheckpointApiModel.parse_obj(data)  # NOTE: this is NOT API model

    # CREATE checkpoint WITHOUT changes
    resp = await client.post(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints",
        json={"tag": "v2", "message": "second commit"},
    )
    data, _ = await assert_status(resp, web.HTTPCreated)

    assert data
    checkpoint2 = CheckpointApiModel.parse_obj(data)  # NOTE: this is NOT API model

    assert (
        checkpoint1 == checkpoint2
    ), "Consecutive create w/o changes shall not add a new checkpoint"


async def test_delete_project_and_repo(
    client: TestClient,
    user_id: UserID,
    project_uuid: ProjectID,
    request_delete_project: Callable[[TestClient, UUID], Awaitable],
):

    # CREATE a checkpoint
    resp = await client.post(
        f"/{VX}/repos/projects/{project_uuid}/checkpoints",
        json={"tag": "v1", "message": "first commit"},
    )
    data, _ = await assert_status(resp, web.HTTPCreated)

    # LIST
    resp = await client.get(f"/{VX}/repos/projects/{project_uuid}/checkpoints")
    await assert_resp_page(
        resp,
        expected_page_cls=Page[CheckpointApiModel],
        expected_total=1,
        expected_count=1,
    )

    # DELETE project -> projects_vc_*  deletion follow
    await request_delete_project(client, project_uuid)

    # TMP fix here waits ------------
    # FIXME: mark as deleted, still gets entrypoints!!
    from simcore_service_webserver.projects import projects_api

    delete_task = projects_api.get_delete_project_task(project_uuid, user_id)
    assert delete_task
    await delete_task
    # --------------------------------

    # LIST empty
    resp = await client.get(f"/{VX}/repos/projects/{project_uuid}/checkpoints")
    await assert_resp_page(
        resp,
        expected_page_cls=Page[CheckpointApiModel],
        expected_total=0,
        expected_count=0,
    )

    # GET HEAD
    resp = await client.get(f"/{VX}/repos/projects/{project_uuid}/HEAD")
    await assert_status(resp, web.HTTPNotFound)
