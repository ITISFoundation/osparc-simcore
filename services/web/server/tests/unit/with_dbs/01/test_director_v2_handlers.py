# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from pytest_simcore.helpers.utils_webserver_unit_with_db import (
    ExpectedResponse,
    standard_role_response,
)
from pytest_simcore.services_api_mocks_for_aiohttp_clients import AioResponsesMock
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.director_v2 import api


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_start_computation(
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
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
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app

    url = client.app.router["start_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(
        f"{url}", json={"subgraph": ["node_id1", "node_id2", "node_id498"]}
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
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["get_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.get(f"{url}")
    await assert_status(rsp, web.HTTPOk if user_role == UserRole.GUEST else expected.ok)


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_stop_computation(
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
    logged_user: LoggedUser,
    project_id: ProjectID,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["stop_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(f"{url}")
    await assert_status(
        rsp, web.HTTPNoContent if user_role == UserRole.GUEST else expected.no_content
    )


async def test_regression_get_dynamic_services_empty_params(
    director_v2_service_mock: AioResponsesMock,
    client: TestClient,
):
    assert client.app
    list_of_services = await api.list_dynamic_services(client.app)
    assert list_of_services == []
