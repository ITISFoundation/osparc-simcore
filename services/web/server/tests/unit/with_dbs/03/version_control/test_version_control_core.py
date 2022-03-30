# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Callable, Dict
from uuid import UUID

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from faker import Faker
from simcore_service_webserver._constants import RQT_USERID_KEY
from simcore_service_webserver.projects import projects_api
from simcore_service_webserver.version_control_core import (
    checkout_checkpoint,
    create_checkpoint,
    list_checkpoints,
    update_checkpoint,
)
from simcore_service_webserver.version_control_db import HEAD, VersionControlRepository

ProjectDict = Dict[str, Any]


# HELPERS


# FIXTURES


@pytest.fixture
def aiohttp_mocked_request(client: TestClient, user_id: int) -> web.Request:
    req = make_mocked_request("GET", "/", app=client.app)
    req[RQT_USERID_KEY] = user_id
    return req


# TESTS


@pytest.mark.acceptance_test
async def test_workflow(
    project_uuid: UUID,
    faker: Faker,
    user_id: int,
    user_project: ProjectDict,
    aiohttp_mocked_request: web.Request,
    do_update_user_project: Callable,
    director_v2_service_mock: None,
):
    vc_repo = VersionControlRepository(aiohttp_mocked_request)

    # -------------------------------------
    checkpoint1 = await create_checkpoint(
        vc_repo, project_uuid, tag="v0", message="first commit"
    )

    assert not checkpoint1.parents_ids
    assert checkpoint1.tags == ("v0",)
    assert checkpoint1.message == "first commit"

    # -------------------------------------
    await do_update_user_project(project_uuid)

    checkpoint2 = await create_checkpoint(
        vc_repo, project_uuid, tag="v1", message="second commit"
    )

    assert checkpoint2.tags == ("v1",)
    assert (checkpoint1.id,) == checkpoint2.parents_ids
    assert checkpoint1.checksum != checkpoint2.checksum

    # -------------------------------------
    checkpoints, total_count = await list_checkpoints(vc_repo, project_uuid)
    assert total_count == 2
    assert checkpoints == [checkpoint2, checkpoint1]

    # -------------------------------------
    checkpoint2_updated = await update_checkpoint(
        vc_repo, project_uuid, HEAD, message="updated message"
    )

    assert checkpoint2_updated.dict(exclude={"message"}) == checkpoint2.dict(
        exclude={"message"}
    )

    # -------------------------------------
    # checking out to v1
    checkpoint_co = await checkout_checkpoint(vc_repo, project_uuid, checkpoint1.id)
    assert checkpoint1 == checkpoint_co

    project = await projects_api.get_project_for_user(
        aiohttp_mocked_request.app, str(project_uuid), user_id
    )
    assert project["workbench"] == user_project["workbench"]

    # -------------------------------------
    # creating branches
    await do_update_user_project(project_uuid)

    checkpoint3 = await create_checkpoint(
        vc_repo,
        project_uuid,
        tag="v1.1",
        message="second commit",  # new_branch="v1.*"
    )

    checkpoints, total_count = await list_checkpoints(vc_repo, project_uuid)
    assert total_count == 3
    assert checkpoints == [checkpoint3, checkpoint2_updated, checkpoint1]

    assert checkpoint3.parents_ids == checkpoint2.parents_ids
    assert checkpoint2.parents_ids == (checkpoint1.id,)
    # This is detached!
