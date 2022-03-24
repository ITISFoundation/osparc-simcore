# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import AsyncIterator, Dict

import pytest
from _helpers import ExpectedResponse, standard_role_response
from aiohttp import web
from aioresponses import aioresponses
from faker import Faker
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver import director_v2_api
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.director_v2_models import (
    ClusterCreate,
    ClusterPatch,
    ClusterPing,
)


@pytest.fixture()
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> AsyncIterator[aioresponses]:
    yield director_v2_service_mock


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return UserID(faker.pyint(min_value=1))


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.fixture
def cluster_id(faker: Faker) -> ClusterID:
    return ClusterID(faker.pyint(min_value=0))


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


async def test_create_pipeline(
    mocked_director_v2, client, user_id: UserID, project_id: ProjectID
):
    task_out = await director_v2_api.create_or_update_pipeline(
        client.app, user_id, project_id
    )
    assert task_out
    assert task_out["state"] == RunningState.NOT_STARTED


async def test_get_computation_task(
    mocked_director_v2,
    client,
    user_id: UserID,
    project_id: ProjectID,
):
    task_out = await director_v2_api.get_computation_task(
        client.app, user_id, project_id
    )
    assert task_out
    assert task_out.state == RunningState.NOT_STARTED


async def test_delete_pipeline(
    mocked_director_v2, client, user_id: UserID, project_id: ProjectID
):
    await director_v2_api.delete_pipeline(client.app, user_id, project_id)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(cluster_create=st.builds(ClusterCreate))
async def test_create_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_create
):
    created_cluster = await director_v2_api.create_cluster(
        client.app, user_id=user_id, new_cluster=cluster_create
    )
    assert created_cluster is not None
    assert isinstance(created_cluster, dict)
    assert "id" in created_cluster


async def test_list_clusters(mocked_director_v2, client, user_id: UserID):
    list_of_clusters = await director_v2_api.list_clusters(client.app, user_id=user_id)
    assert isinstance(list_of_clusters, list)
    assert len(list_of_clusters) > 0


async def test_get_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID
):
    cluster = await director_v2_api.get_cluster(
        client.app, user_id=user_id, cluster_id=cluster_id
    )
    assert isinstance(cluster, dict)
    assert cluster["id"] == cluster_id


async def test_get_cluster_details(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID
):
    cluster_details = await director_v2_api.get_cluster_details(
        client.app, user_id=user_id, cluster_id=cluster_id
    )
    assert isinstance(cluster_details, dict)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(cluster_patch=st.from_type(ClusterPatch))
async def test_update_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID, cluster_patch
):
    print(f"--> updating cluster with {cluster_patch=}")
    updated_cluster = await director_v2_api.update_cluster(
        client.app, user_id=user_id, cluster_id=cluster_id, cluster_patch=cluster_patch
    )
    assert isinstance(updated_cluster, dict)
    assert updated_cluster["id"] == cluster_id


async def test_delete_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID
):
    await director_v2_api.delete_cluster(
        client.app, user_id=user_id, cluster_id=cluster_id
    )


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(cluster_ping=st.builds(ClusterPing))
async def test_ping_cluster(mocked_director_v2, client, cluster_ping: ClusterPing):
    await director_v2_api.ping_cluster(client.app, cluster_ping=cluster_ping)
