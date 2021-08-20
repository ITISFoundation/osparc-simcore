# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Dict

from aiohttp import web
from models_library.projects import Project
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver._meta import api_vtag as vtag
from simcore_service_webserver.snapshots_models import SnapshotItem

ProjectDict = Dict[str, Any]


async def test_create_snapshot_workflow(client, user_project: ProjectDict):

    project_uuid = user_project["uuid"]

    # get existing project
    resp = await client.get(f"/{vtag}/projects/{project_uuid}")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data
    project = Project.parse_obj(data)

    # list snapshots -> None
    resp = await client.get(f"/{vtag}/projects/{project_uuid}/snapshots")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data == []

    # create snapshot
    resp = await client.post(f"/{vtag}/projects/{project_uuid}/snapshots")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data
    snapshot = SnapshotItem.parse_obj(data)

    assert snapshot.parent_uuid == project.uuid

    # snapshot has an associated project
    resp = await client.get(f"/{vtag}/projects/{snapshot.project_uuid}")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert data
    snapshot_project = Project.parse_obj(data)

    # FIXME: project is None and snapshot_project is {}
    project.ui.workbench = {}
    project.ui.slideshow = {}

    different_fields = {"name", "uuid", "creation_date", "last_change_date"}
    assert snapshot_project.dict(exclude=different_fields) == project.dict(
        exclude=different_fields
    )

    # snapshot projects are hiddden, and therefore NOT listed
    resp = await client.get(f"/{vtag}/projects")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert len(data) == 1

    # FIXME:
    project.ui.workbench = None
    assert project == Project.parse_obj(data[0])

    # now it has one snapshot
    resp = await client.get(f"/{vtag}/projects/{project_uuid}/snapshots")
    data, _ = await assert_status(resp, web.HTTPOk)

    assert len(data) == 1
    assert snapshot == SnapshotItem.parse_obj(data[0])
