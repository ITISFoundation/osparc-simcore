# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from collections.abc import Callable
from typing import Any, Awaitable

import httpx
import pytest
import sqlalchemy as sa
from _dask_helpers import DaskGatewayServer
from dask_gateway import Gateway, GatewayCluster, auth
from distributed import Client as DaskClient
from distributed.deploy.spec import SpecCluster
from faker import Faker
from models_library.api_schemas_directorv2.clusters import ClusterDetailsGet
from models_library.clusters import Cluster, ClusterID, SimpleAuthentication
from models_library.users import UserID
from pydantic import SecretStr
from pytest_simcore.helpers.typing_env import EnvVarsDict
from starlette import status
from tenacity.asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

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


@pytest.mark.skip(
    reason="test for helping developers understand how to use dask gateways"
)
async def test_local_dask_gateway_server(local_dask_gateway_server: DaskGatewayServer):
    async with Gateway(
        local_dask_gateway_server.address,
        local_dask_gateway_server.proxy_address,
        asynchronous=True,
        auth=auth.BasicAuth("pytest_user", local_dask_gateway_server.password),
    ) as gateway:
        print(f"--> {gateway=} created")
        cluster_options = await gateway.cluster_options()
        gateway_versions = await gateway.get_versions()
        clusters_list = await gateway.list_clusters()
        print(f"--> {gateway_versions=}, {cluster_options=}, {clusters_list=}")
        for option in cluster_options.items():
            print(f"--> {option=}")

        async with gateway.new_cluster() as cluster:
            assert cluster
            print(f"--> created new cluster {cluster=}, {cluster.scheduler_info=}")
            NUM_WORKERS = 10
            await cluster.scale(NUM_WORKERS)
            print(f"--> scaling cluster {cluster=} to {NUM_WORKERS} workers")
            async for attempt in AsyncRetrying(
                reraise=True, wait=wait_fixed(0.24), stop=stop_after_delay(30)
            ):
                with attempt:
                    print(
                        f"cluster {cluster=} has now {len(cluster.scheduler_info.get('workers', []))} worker(s)"
                    )
                    assert len(cluster.scheduler_info.get("workers", 0)) == 10

            async with cluster.get_client() as client:
                print(f"--> created new client {client=}, submitting a job")
                res = await client.submit(lambda x: x + 1, 1)
                assert res == 2

            print(f"--> scaling cluster {cluster=} back to 0")
            await cluster.scale(0)

            async for attempt in AsyncRetrying(
                reraise=True, wait=wait_fixed(0.24), stop=stop_after_delay(30)
            ):
                with attempt:
                    print(
                        f"cluster {cluster=} has now {len(cluster.scheduler_info.get('workers', []))}"
                    )
                    assert len(cluster.scheduler_info.get("workers", 0)) == 0


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
    local_dask_gateway_server: DaskGatewayServer,
    create_cluster: Callable[..., Awaitable[Cluster]],
    dask_gateway_cluster: GatewayCluster,
    dask_gateway_cluster_client: DaskClient,
    gateway_username: str,
):
    user_1 = registered_user()
    # define the cluster in the DB
    some_cluster = await create_cluster(
        user_1,
        endpoint=local_dask_gateway_server.address,
        authentication=SimpleAuthentication(
            username=gateway_username,
            password=SecretStr(local_dask_gateway_server.password),
        ).model_dump(by_alias=True),
    )
    # in its present state, the cluster should have no workers
    cluster_out = await _get_cluster_details(
        async_client, user_1["id"], some_cluster.id
    )
    assert not cluster_out.scheduler.workers, "the cluster should not have any worker!"

    # now let's scale the cluster
    _NUM_WORKERS = 1
    await dask_gateway_cluster.scale(_NUM_WORKERS)
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(60), wait=wait_fixed(1)
    ):
        with attempt:
            cluster_out = await _get_cluster_details(
                async_client, user_1["id"], some_cluster.id
            )
            assert cluster_out.scheduler.workers, "the cluster has no workers!"
            assert (
                len(cluster_out.scheduler.workers) == _NUM_WORKERS
            ), f"the cluster is expected to have {_NUM_WORKERS} worker(s), currently has {len(cluster_out.scheduler.workers)} worker(s)"
            print(
                f"cluster now has its {_NUM_WORKERS}, after {json.dumps(attempt.retry_state.retry_object.statistics)}"
            )
    print(f"!!> cluster dashboard link: {dask_gateway_cluster.dashboard_link}")

    # let's start some computation
    _TASK_SLEEP_TIME = 55

    def do_some_work(x: int):
        import time

        time.sleep(x)
        return True

    task = dask_gateway_cluster_client.submit(do_some_work, _TASK_SLEEP_TIME)
    # wait for the computation to start, we should see this in the cluster infos
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(10), wait=wait_fixed(1)
    ):
        with attempt:
            cluster_out = await _get_cluster_details(
                async_client, user_1["id"], some_cluster.id
            )
            assert cluster_out.scheduler.workers
            assert (
                next(
                    iter(cluster_out.scheduler.workers.values())
                ).metrics.task_counts.executing
                == 1
            ), "worker is not executing the task"
            print(
                f"!!> cluster metrics: {next(iter(cluster_out.scheduler.workers.values())).metrics=}"
            )
    # let's wait for the result
    result = task.result(timeout=_TASK_SLEEP_TIME + 5)
    assert result
    assert await result is True
    # wait for the computation to effectively stop
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(60), wait=wait_fixed(1)
    ):
        with attempt:
            cluster_out = await _get_cluster_details(
                async_client, user_1["id"], some_cluster.id
            )
            assert cluster_out.scheduler.workers
            print(
                f"!!> cluster metrics: {next(iter(cluster_out.scheduler.workers.values())).metrics=}"
            )
            assert (
                next(
                    iter(cluster_out.scheduler.workers.values())
                ).metrics.task_counts.executing
                == 0
            ), "worker is still executing the task"
            assert (
                next(
                    iter(cluster_out.scheduler.workers.values())
                ).metrics.task_counts.memory
                == 1
            ), "worker did not keep the result in memory"
            # NOTE: this is a CPU percent use
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.cpu < 5.0
            ), "worker did not update the cpu metrics"

    # since the task is completed the worker should have stopped executing
    cluster_out = await _get_cluster_details(
        async_client, user_1["id"], some_cluster.id
    )
    assert cluster_out.scheduler.workers
    worker_data = next(iter(cluster_out.scheduler.workers.values()))
    assert worker_data.metrics.task_counts.executing == 0
    # in dask, the task remains in memory until the result is deleted
    assert worker_data.metrics.task_counts.memory == 1
