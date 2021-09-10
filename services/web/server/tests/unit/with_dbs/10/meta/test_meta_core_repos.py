# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Dict
from uuid import UUID

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from faker import Faker
from simcore_service_webserver.constants import RQT_USERID_KEY
from simcore_service_webserver.meta_core_repos import (
    HEAD,
    checkout_checkpoint,
    create_checkpoint,
    list_checkpoints,
    update_checkpoint,
)
from simcore_service_webserver.meta_db import VersionControlRepository
from simcore_service_webserver.projects import projects_api

ProjectDict = Dict[str, Any]


# HELPERS


async def user_modifies_project(project_uuid: UUID, faker: Faker):
    new_workbench = {faker.uuid4(): {"x": faker.pyint(), "y": faker.pyint()}}


# FIXTURES


@pytest.fixture()
def project_uuid(user_project: ProjectDict) -> UUID:
    return UUID(user_project["uuid"])


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
):
    vc_repo = VersionControlRepository(aiohttp_mocked_request)

    # -------------------------------------
    checkpoint1 = await create_checkpoint(
        vc_repo, project_uuid, tag="v0", message="first commit"
    )

    assert not checkpoint1.parents_ids
    assert checkpoint1.tags == ("v0",)
    assert checkpoint1.message == "first commit"

    # TODO: project w/o changes, raise error .. or add new tag?

    # -------------------------------------
    await user_modifies_project(project_uuid, faker)

    project = await projects_api.get_project_for_user(
        aiohttp_mocked_request.app, str(project_uuid), user_id
    )
    assert project != user_project

    checkpoint2 = await create_checkpoint(
        vc_repo, project_uuid, tag="v1", message="second commit"
    )

    assert checkpoint2.tags == ("v1",)
    assert (checkpoint1.id,) == checkpoint2.parents_ids

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
    assert project == user_project

    # -------------------------------------
    # creating branches

    await user_modifies_project(project_uuid, faker)
    checkpoint2 = await create_checkpoint(
        vc_repo,
        project_uuid,
        tag="v1.1",
        message="second commit",  # new_branch="v1.*"
    )
