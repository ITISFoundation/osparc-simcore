# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from typing import AsyncIterator, Dict

import pytest
from _helpers import ExpectedResponse, standard_role_response
from aiohttp import web
from aioresponses import aioresponses
from faker import Faker
from models_library.projects import ProjectID
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.db_models import UserRole


@pytest.fixture()
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> AsyncIterator[aioresponses]:
    yield director_v2_service_mock


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_pipeline(
    mocked_director_v2,
    client,
    logged_user: Dict,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["start_pipeline"].url_for(project_id=f"{project_id}")
    rsp = await client.post(url)
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


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_partial_pipeline(
    mocked_director_v2,
    client,
    logged_user: Dict,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["start_pipeline"].url_for(project_id=f"{project_id}")
    rsp = await client.post(
        url, json={"subgraph": ["node_id1", "node_id2", "node_id498"]}
    )
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


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_get_pipeline(
    mocked_director_v2,
    client,
    logged_user: Dict,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["get_pipeline"].url_for(project_id=f"{project_id}")
    rsp = await client.get(url)
    await assert_status(rsp, web.HTTPOk if user_role == UserRole.GUEST else expected.ok)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_stop_pipeline(
    mocked_director_v2,
    client,
    logged_user: Dict,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["stop_pipeline"].url_for(project_id=f"{project_id}")
    rsp = await client.post(url)
    await assert_status(
        rsp, web.HTTPNoContent if user_role == UserRole.GUEST else expected.no_content
    )
