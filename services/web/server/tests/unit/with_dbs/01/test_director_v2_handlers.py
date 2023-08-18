# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from typing import AsyncIterator

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from faker import Faker
from models_library.projects import ProjectID
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_webserver_unit_with_db import (
    ExpectedResponse,
    standard_role_response,
)
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.director_v2 import api


@pytest.fixture()
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> AsyncIterator[aioresponses]:
    yield director_v2_service_mock


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_computation(
    mocked_director_v2,
    client: TestClient,
    logged_user: dict,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app

    url = client.app.router["start_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(f"{url}")
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
async def test_start_partial_computation(
    mocked_director_v2,
    client,
    logged_user: dict,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["start_computation"].url_for(project_id=f"{project_id}")
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
async def test_get_computation(
    mocked_director_v2,
    client,
    logged_user: dict,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["get_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.get(url)
    await assert_status(rsp, web.HTTPOk if user_role == UserRole.GUEST else expected.ok)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_stop_computation(
    mocked_director_v2,
    client,
    logged_user: dict,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    url = client.app.router["stop_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(url)
    await assert_status(
        rsp, web.HTTPNoContent if user_role == UserRole.GUEST else expected.no_content
    )


async def test_regression_get_dynamic_services_empty_params(
    mocked_director_v2,
    client,
):
    list_of_services = await api.list_dynamic_services(client.app)
    assert list_of_services == []
