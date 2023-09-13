# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aioresponses import aioresponses
from faker import Faker
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from models_library.api_schemas_webserver.clusters import (
    ClusterCreate,
    ClusterPatch,
    ClusterPing,
)
from models_library.clusters import ClusterID
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_service_webserver.director_v2 import api


@pytest.fixture()
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    return director_v2_service_mock


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return UserID(faker.pyint(min_value=1))


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.fixture
def cluster_id(faker: Faker) -> ClusterID:
    return ClusterID(faker.pyint(min_value=0))


async def test_create_pipeline(
    mocked_director_v2,
    client,
    user_id: UserID,
    project_id: ProjectID,
    osparc_product_name: str,
):
    task_out = await api.create_or_update_pipeline(
        client.app, user_id, project_id, osparc_product_name
    )
    assert task_out
    assert isinstance(task_out, dict)
    assert task_out["state"] == RunningState.NOT_STARTED


async def test_get_computation_task(
    mocked_director_v2,
    client,
    user_id: UserID,
    project_id: ProjectID,
):
    task_out = await api.get_computation_task(client.app, user_id, project_id)
    assert task_out
    assert isinstance(task_out, ComputationTask)
    assert task_out.state == RunningState.NOT_STARTED


async def test_delete_pipeline(
    mocked_director_v2, client, user_id: UserID, project_id: ProjectID
):
    await api.delete_pipeline(client.app, user_id, project_id)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(cluster_create=st.builds(ClusterCreate))
async def test_create_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_create
):
    created_cluster = await api.create_cluster(
        client.app, user_id=user_id, new_cluster=cluster_create
    )
    assert created_cluster is not None
    assert isinstance(created_cluster, dict)
    assert "id" in created_cluster


async def test_list_clusters(mocked_director_v2, client, user_id: UserID):
    list_of_clusters = await api.list_clusters(client.app, user_id=user_id)
    assert isinstance(list_of_clusters, list)
    assert len(list_of_clusters) > 0


async def test_get_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID
):
    cluster = await api.get_cluster(client.app, user_id=user_id, cluster_id=cluster_id)
    assert isinstance(cluster, dict)
    assert cluster["id"] == cluster_id


async def test_get_cluster_details(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID
):
    cluster_details = await api.get_cluster_details(
        client.app, user_id=user_id, cluster_id=cluster_id
    )
    assert isinstance(cluster_details, dict)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(cluster_patch=st.from_type(ClusterPatch))
async def test_update_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID, cluster_patch
):
    print(f"--> updating cluster with {cluster_patch=}")
    updated_cluster = await api.update_cluster(
        client.app, user_id=user_id, cluster_id=cluster_id, cluster_patch=cluster_patch
    )
    assert isinstance(updated_cluster, dict)
    assert updated_cluster["id"] == cluster_id


async def test_delete_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID
):
    await api.delete_cluster(client.app, user_id=user_id, cluster_id=cluster_id)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(cluster_ping=st.builds(ClusterPing))
async def test_ping_cluster(mocked_director_v2, client, cluster_ping: ClusterPing):
    await api.ping_cluster(client.app, cluster_ping=cluster_ping)


async def test_ping_specific_cluster(
    mocked_director_v2, client, user_id: UserID, cluster_id: ClusterID
):
    await api.ping_specific_cluster(client.app, user_id=user_id, cluster_id=cluster_id)
