# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from pytest_simcore.services_api_mocks_for_aiohttp_clients import AioResponsesMock
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole


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
        rsp,
        status.HTTP_201_CREATED if user_role == UserRole.GUEST else expected.created,
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
    faker: Faker,
):
    assert client.app

    url = client.app.router["start_computation"].url_for(project_id=f"{project_id}")
    rsp = await client.post(
        f"{url}", json={"subgraph": [faker.uuid4(), faker.uuid4(), faker.uuid4()]}
    )
    data, error = await assert_status(
        rsp,
        status.HTTP_201_CREATED if user_role == UserRole.GUEST else expected.created,
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
    await assert_status(
        rsp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
    )


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
        rsp,
        (
            status.HTTP_204_NO_CONTENT
            if user_role == UserRole.GUEST
            else expected.no_content
        ),
    )
