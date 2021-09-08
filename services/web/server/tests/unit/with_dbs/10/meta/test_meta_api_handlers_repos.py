# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Dict

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects import Project
from openapi_core.schema.specs.models import Spec
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver import meta_api_handlers_repos
from simcore_service_webserver._meta import api_vtag as vtag
from simcore_service_webserver.meta_models_repos import Checkpoint

ProjectDict = Dict[str, Any]


@pytest.mark.parametrize(
    "route",
    meta_api_handlers_repos.routes,
    ids=lambda r: f"{r.method.upper()} {r.path}",
)
def test_route_against_openapi_specs(route, openapi_specs: Spec):

    assert route.path.startswith(f"/{vtag}")
    path = route.path.replace(f"/{vtag}", "")

    assert (
        route.method.lower() in openapi_specs.paths[path].operations
    ), f"operation {route.method} undefined in OAS"

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), "route's name differs from OAS operation_id"


async def test_workflow(client: TestClient, user_project: ProjectDict):

    project_uuid = user_project["uuid"]

    # get existing project
    resp = await client.get(f"/{vtag}/projects/{project_uuid}")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data
    project = Project.parse_obj(data)
    assert project.uuid == project_uuid

    # list repos i.e. versioned projects
    resp = await client.get(f"/{vtag}/repos/projects")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == []

    # create a checkpoint
    resp = await client.post(
        f"/{vtag}/projects/{project_uuid}/checkpoints",
        json={"tag": "v1", "message": "init"},
    )
    data, _ = await assert_status(resp, web.HTTPCreated)

    assert data
    checkpoint = Checkpoint.parse_obj(data)  # NOTE: this is NOT API model
