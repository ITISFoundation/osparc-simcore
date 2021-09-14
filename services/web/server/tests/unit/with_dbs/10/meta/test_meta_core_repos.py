# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from typing import Any, Callable, Dict
from uuid import UUID

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from faker import Faker
from pytest_simcore.helpers.utils_login import UserDict
from simcore_service_webserver._meta import api_vtag as vtag
from simcore_service_webserver.constants import RQT_USERID_KEY
from simcore_service_webserver.meta_core_repos import (
    checkout_checkpoint,
    create_checkpoint,
    list_checkpoints,
    update_checkpoint,
)
from simcore_service_webserver.meta_db import HEAD, VersionControlRepository
from simcore_service_webserver.projects import projects_api

ProjectDict = Dict[str, Any]


# HELPERS


# FIXTURES


@pytest.fixture()
def project_uuid(user_project: ProjectDict) -> UUID:
    return UUID(user_project["uuid"])


@pytest.fixture
def aiohttp_mocked_request(client: TestClient, user_id: int) -> web.Request:
    req = make_mocked_request("GET", "/", app=client.app)
    req[RQT_USERID_KEY] = user_id
    return req


@pytest.fixture
def user_modifier(logged_user: UserDict, client: TestClient, faker: Faker) -> Callable:
    async def go(project_uuid: UUID):

        resp: aiohttp.ClientResponse = await client.get(
            f"{vtag}/projects/{project_uuid}"
        )

        assert resp.status == 200
        body = await resp.json()
        assert body

        project = body["data"]
        project["workbench"] = {
            faker.uuid4(): {
                "key": f"simcore/services/comp/test_{__name__}",
                "version": "1.0.0",
                "label": f"test_{__name__}",
                "inputs": {"x": faker.pyint(), "y": faker.pyint()},
            }
        }
        resp = await client.put(f"{vtag}/projects/{project_uuid}", json=project)
        body = await resp.json()
        assert resp.status == 200, str(body)

    return go


# TESTS


@pytest.mark.acceptance_test
async def test_workflow(
    project_uuid: UUID,
    faker: Faker,
    user_id: int,
    user_project: ProjectDict,
    aiohttp_mocked_request: web.Request,
    user_modifier: Callable,
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
    await user_modifier(project_uuid)

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
    await user_modifier(project_uuid)

    checkpoint3 = await create_checkpoint(
        vc_repo,
        project_uuid,
        tag="v1.1",
        message="second commit",  # new_branch="v1.*"
    )

    checkpoints, total_count = await list_checkpoints(vc_repo, project_uuid)
    assert total_count == 3
    assert checkpoints == [checkpoint3, checkpoint2, checkpoint1]

    assert checkpoint3.parents_ids == checkpoint2.parents_ids
    assert checkpoint2.parents_ids == (checkpoint1.id,)
    # This is detached!
