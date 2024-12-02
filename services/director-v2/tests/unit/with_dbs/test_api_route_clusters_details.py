# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
import sqlalchemy as sa
from distributed.deploy.spec import SpecCluster
from faker import Faker
from models_library.api_schemas_directorv2.clusters import ClusterDetailsGet
from models_library.clusters import Cluster, ClusterID, SimpleAuthentication
from models_library.users import UserID
from pydantic import SecretStr
from pytest_simcore.helpers.typing_env import EnvVarsDict
from starlette import status

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
def clusters_config(
    mock_env: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    dask_spec_local_cluster: SpecCluster,
    faker: Faker,
):
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())


async def test_get_default_cluster_details(
    clusters_config: None,
    registered_user: Callable,
    async_client: httpx.AsyncClient,
):
    user_1 = registered_user()

    # This test checks that the default cluster is accessible
    # the default cluster is the osparc internal cluster available through a dask-scheduler
    response = await async_client.get(
        f"/v2/clusters/default/details?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_200_OK
    default_cluster_out = ClusterDetailsGet.model_validate(response.json())
    response = await async_client.get(
        f"/v2/clusters/{0}/details?user_id={user_1['id']}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert default_cluster_out == ClusterDetailsGet.model_validate(response.json())


async def _get_cluster_details(
    async_client: httpx.AsyncClient, user_id: UserID, cluster_id: ClusterID
) -> ClusterDetailsGet:
    response = await async_client.get(
        f"/v2/clusters/{cluster_id}/details?user_id={user_id}"
    )
    assert response.status_code == status.HTTP_200_OK
    print(f"<-- received cluster details response {response=}")
    cluster_out = ClusterDetailsGet.model_validate(response.json())
    assert cluster_out
    print(f"<-- received cluster details {cluster_out=}")
    assert cluster_out.scheduler, "the cluster's scheduler is not started!"
    return cluster_out


async def test_get_cluster_details(
    clusters_config: None,
    registered_user: Callable[..., dict[str, Any]],
    async_client: httpx.AsyncClient,
    create_cluster: Callable[..., Awaitable[Cluster]],
    faker: Faker,
):
    user_1 = registered_user()
    # define the cluster in the DB
    some_cluster = await create_cluster(
        user_1,
        endpoint=faker.uri(),
        authentication=SimpleAuthentication(
            username=faker.user_name(),
            password=SecretStr(faker.password()),
        ).model_dump(by_alias=True),
    )
    # in its present state, the cluster should have no workers
    cluster_out = await _get_cluster_details(
        async_client, user_1["id"], some_cluster.id
    )
    assert not cluster_out.scheduler.workers, "the cluster should not have any worker!"
