# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Dict
from uuid import UUID

import pytest
from aiohttp import web
from faker import Faker
from simcore_service_webserver.meta_core_repos import (
    HEAD,
    checkout_checkpoint,
    create_checkpoint,
    list_checkpoints,
    update_checkpoint,
)
from simcore_service_webserver.projects import projects_api

ProjectDict = Dict[str, Any]


# HELPERS


async def user_modifies_project(project_uuid: UUID, faker: Faker):
    new_workbench = {faker.uuid4(): {"x": faker.pyint(), "y": faker.pyint()}}


# FIXTURES


@pytest.fixture()
def project_uuid(user_project: ProjectDict) -> UUID:
    return UUID(user_project["uuid"])


# TESTS


async def test_workflow(
    app: web.Application,
    project_uuid: UUID,
    faker: Faker,
    user_project: ProjectDict,
    user_id: int,
):

    # -------------------------------------
    checkpoint1 = await create_checkpoint(
        app, project_uuid, tag="v0", message="first commit"
    )

    assert not checkpoint1.parents
    assert checkpoint1.tag == "v0"
    assert checkpoint1.message == "first commit"
    assert checkpoint1.branch == "main"

    # TODO: project w/o changes, raise error .. or add new tag?

    # -------------------------------------
    await user_modifies_project(project_uuid, faker)
    project = await projects_api.get_project_for_user(app, project_uuid, user_id)
    assert project != user_project

    checkpoint2 = await create_checkpoint(
        app, project_uuid, tag="v1", message="second commit"
    )

    assert checkpoint2.tag == "v1"
    assert [{"sha": checkpoint1.id}] == checkpoint2.parents

    # -------------------------------------
    checkpoints = await list_checkpoints(app)
    assert checkpoints == [checkpoint2, checkpoint1]

    # -------------------------------------
    checkpoint2_updated = await update_checkpoint(
        app, project_uuid, HEAD, message="updated message"
    )

    assert checkpoint2_updated.dict(exclude={"message"}) == checkpoint2.dict(
        exclude={"message"}
    )

    # -------------------------------------
    # checking out to v1
    checkpoint_co = await checkout_checkpoint(app, project_uuid, checkpoint1.id)
    assert checkpoint1 == checkpoint_co

    project = await projects_api.get_project_for_user(app, str(project_uuid), user_id)
    assert project == user_project

    # -------------------------------------
    # creating branches

    await user_modifies_project(project_uuid, faker)
    checkpoint2 = await create_checkpoint(
        app, project_uuid, tag="v1.1", message="second commit", new_branch="v1.*"
    )
