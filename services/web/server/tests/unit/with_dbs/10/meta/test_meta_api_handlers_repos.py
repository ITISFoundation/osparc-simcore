# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Dict, Type
from uuid import UUID

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects import Project
from pydantic.main import BaseModel
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.rest_pagination_utils import PageResponseLimitOffset
from simcore_service_webserver._meta import api_vtag as vtag
from simcore_service_webserver.meta_models_repos import CheckpointApiModel, RepoApiModel

ProjectDict = Dict[str, Any]

# HELPERS


async def assert_resp_page(
    resp: aiohttp.ClientResponse, expected_total: int, expected_count: int
) -> PageResponseLimitOffset:
    assert resp.status == web.HTTPOk.status_code, f"Got {await resp.text()}"
    body = await resp.json()

    page = PageResponseLimitOffset.parse_obj(body)
    assert page.meta.total == expected_total
    assert page.meta.count == expected_count
    return page


async def assert_status_and_body(
    resp, expected_cls: Type[web.HTTPException], expected_model: Type[BaseModel]
) -> BaseModel:
    data, _ = await assert_status(resp, expected_cls)
    model = expected_model.parse_obj(data)
    return model


# FIXTURES


# TESTS


@pytest.mark.acceptance_test
async def test_workflow(client: TestClient, user_project: ProjectDict):

    project_uuid = user_project["uuid"]

    # get existing project
    resp = await client.get(f"/{vtag}/projects/{project_uuid}")
    data, _ = await assert_status(resp, web.HTTPOk)
    project = Project.parse_obj(data)
    assert project.uuid == UUID(project_uuid)

    #
    # list repos i.e. versioned projects
    resp = await client.get(f"/{vtag}/repos/projects")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == []

    #
    # CREATE a checkpoint
    resp = await client.post(
        f"/{vtag}/repos/projects/{project_uuid}/checkpoints",
        json={"tag": "v1", "message": "init"},
    )
    data, _ = await assert_status(resp, web.HTTPCreated)

    assert data
    checkpoint1 = CheckpointApiModel.parse_obj(data)  # NOTE: this is NOT API model

    #
    # this project now has a repo
    resp = await client.get(f"/{vtag}/repos/projects")
    page = await assert_resp_page(resp, expected_total=1, expected_count=1)

    repo = RepoApiModel.parse_obj(page.data[0])
    assert repo.project_uuid == UUID(project_uuid)

    # GET checkpoint with HEAD
    resp = await client.get(f"/{vtag}/repos/projects/{project_uuid}/checkpoints/HEAD")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert CheckpointApiModel.parse_obj(data) == checkpoint1

    # GET checkpoint with tag
    resp = await client.get(f"/{vtag}/repos/projects/{project_uuid}/checkpoints/v1")
    assert CheckpointApiModel.parse_obj(data) == checkpoint1

    # GET checkpoint with id
    resp = await client.get(
        f"/{vtag}/repos/projects/{project_uuid}/checkpoints/{checkpoint1.id}"
    )
    assert str(resp.url) == checkpoint1.url
    assert CheckpointApiModel.parse_obj(data) == checkpoint1

    # LIST checkpoints
    resp = await client.get(f"/{vtag}/repos/projects/{project_uuid}/checkpoints")
    page = await assert_resp_page(resp, expected_total=1, expected_count=1)

    assert CheckpointApiModel.parse_obj(page.data[0]) == checkpoint1

    # UPDATE checkpoint annotations
    resp = await client.patch(
        f"/{vtag}/repos/projects/{project_uuid}/checkpoints/v1",
        json={"tag": "Version1", "message": "updated message"},
    )
    data, _ = await assert_status(resp, web.HTTPOk)
    checkpoint1_updated = CheckpointApiModel.parse_obj(data)

    assert checkpoint1_updated.tag == "Version1"
    assert checkpoint1_updated.message == "updated message"

    # GET view
    resp = await client.get(
        f"/{vtag}/repos/projects/{project_uuid}/checkpoints/HEAD/workbench/view"
    )
    data, _ = await assert_status(resp, web.HTTPOk)
    assert data == project.dict(include={"workbench", "ui"})

    # do some changes in project
    # TODO:

    # CREATE new checkpoint
    resp = await client.post(
        f"/{vtag}/repos/projects/{project_uuid}/checkpoints",
        json={"tag": "v2", "message": "new commit"},
    )
    data, _ = await assert_status(resp, web.HTTPCreated)
    checkpoint2 = CheckpointApiModel.parse_obj(data)
    assert checkpoint2.tag == "v2"

    # GET checkpoint with HEAD
    resp = await client.get(f"/{vtag}/repos/projects/{project_uuid}/checkpoints/HEAD")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert CheckpointApiModel.parse_obj(data) == checkpoint2

    # CHECKOUT
    resp = await client.get(
        f"/{vtag}/repos/projects/{project_uuid}/checkpoints/Version1"
    )
    data, _ = await assert_status(resp, web.HTTPOk)
    assert CheckpointApiModel.parse_obj(data) == checkpoint1_updated

    # GET checkpoint with HEAD
    resp = await client.get(f"/{vtag}/repos/projects/{project_uuid}/checkpoints/HEAD")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert CheckpointApiModel.parse_obj(data) == checkpoint1_updated

    # get working copy
    resp = await client.get(f"/{vtag}/projects/{project_uuid}")
    data, _ = await assert_status(resp, web.HTTPOk)
    project_wc = Project.parse_obj(data)
    assert project_wc.uuid == UUID(project_uuid)
    assert project_wc != project


def test_create_checkpoint_without_changes():
    # create checkpoint

    # create checkpoint without changes
    ...


def test_checkpoint_tags():
    # unique
    # no-spaces
    # only letters and numbers
    ...
