# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import Dict
from uuid import UUID, uuid4
from models_library.nodes import RunningState
from pydantic.types import PositiveInt

import pytest
from aiohttp import web
from aioresponses import aioresponses

from _helpers import ExpectedResponse, standard_role_response
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver import director_v2
from simcore_service_webserver.db_models import UserRole


@pytest.fixture()
async def logged_user(client, user_role: UserRole):
    """adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        print("-----> logged in user as", user_role)
        yield user
        print("<----- logged out user as", user_role)


@pytest.fixture(autouse=True)
async def auto_mock_director_v2(
    loop,
    director_v2_subsystem_mock: aioresponses,
) -> aioresponses:
    yield director_v2_subsystem_mock


@pytest.fixture
def user_id() -> PositiveInt:
    return 123


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


@pytest.mark.parametrize(
    *standard_role_response(),
)
async def test_start_pipeline(
    client,
    logged_user: Dict,
    project_id: UUID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["start_pipeline"].url_for(project_id=f"{project_id}")
    rsp = await client.post(url, json={"user_id": "some id"})
    data, error = await assert_status(
        rsp, web.HTTPCreated if user_role == UserRole.GUEST else expected.created
    )

    if user_role != UserRole.ANONYMOUS:
        assert not error, f"error received: {error}"
    if data:
        assert "pipeline_id" in data
        assert (
            data["pipeline_id"] == f"{project_id}"
        ), f"received pipeline id: {data['pipeline_id']}, expected {project_id}"


@pytest.mark.parametrize(
    *standard_role_response(),
)
async def test_stop_pipeline(
    client,
    logged_user: Dict,
    project_id: UUID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["stop_pipeline"].url_for(project_id=f"{project_id}")
    rsp = await client.post(url, json={"user_id": "some id"})
    await assert_status(
        rsp, web.HTTPNoContent if user_role == UserRole.GUEST else expected.no_content
    )


async def test_get_pipeline_state(
    client,
    user_id: PositiveInt,
    project_id: UUID,
):
    project_running_state = await director_v2.get_pipeline_state(
        client.app, user_id, project_id
    )

    assert project_running_state == RunningState.NOT_STARTED


async def test_delete_pipeline(client, user_id: PositiveInt, project_id: UUID):
    project_running_state = await director_v2.delete_pipeline(
        client.app, user_id, project_id
    )
