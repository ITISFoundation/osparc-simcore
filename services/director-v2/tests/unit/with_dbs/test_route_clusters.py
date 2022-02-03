# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from typing import AsyncIterator, Callable, Dict, Iterable, List

import httpx
import pytest
import sqlalchemy as sa
from _dask_helpers import DaskGatewayServer
from _pytest.monkeypatch import MonkeyPatch
from dask_gateway import Gateway, GatewayCluster, auth
from distributed import Client as DaskClient
from distributed.deploy.spec import SpecCluster
from models_library.clusters import Cluster, SimpleAuthentication
from pydantic import NonNegativeInt
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_service_director_v2.models.schemas.clusters import ClusterOut
from starlette import status
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture()
def clusters_config(
    mock_env: None,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitSettings,
    monkeypatch: MonkeyPatch,
    dask_spec_local_cluster: SpecCluster,
):
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_S3_PROVIDER", "MINIO")


@pytest.fixture
def cluster(
    user_db: Dict,
    postgres_db: sa.engine.Engine,
) -> Iterable[Callable[..., Cluster]]:
    created_cluster_ids: List[str] = []

    def creator(**overrides) -> Cluster:
        cluster_config = Cluster.Config.schema_extra["examples"][0]
        cluster_config["owner"] = user_db["primary_gid"]
        cluster_config.update(**overrides)
        new_cluster = Cluster.parse_obj(cluster_config)
        assert new_cluster

        with postgres_db.connect() as conn:
            created_cluser_id = conn.scalar(
                # pylint: disable=no-value-for-parameter
                clusters.insert()
                .values(new_cluster.to_clusters_db(only_update=False))
                .returning(clusters.c.id)
            )
            created_cluster_ids.append(created_cluser_id)
            result = conn.execute(
                sa.select(
                    [
                        clusters,
                        cluster_to_groups.c.gid,
                        cluster_to_groups.c.read,
                        cluster_to_groups.c.write,
                        cluster_to_groups.c.delete,
                    ]
                )
                .select_from(
                    clusters.join(
                        cluster_to_groups,
                        clusters.c.id == cluster_to_groups.c.cluster_id,
                    )
                )
                .where(clusters.c.id == created_cluser_id)
            )

            row = result.fetchone()
            assert row
            return Cluster.construct(
                id=row[clusters.c.id],
                name=row[clusters.c.name],
                description=row[clusters.c.description],
                type=row[clusters.c.type],
                owner=row[clusters.c.owner],
                endpoint=row[clusters.c.endpoint],
                authentication=row[clusters.c.authentication],
                access_rights={
                    row[clusters.c.owner]: {
                        "read": row[cluster_to_groups.c.read],
                        "write": row[cluster_to_groups.c.write],
                        "delete": row[cluster_to_groups.c.delete],
                    }
                },
            )

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            # pylint: disable=no-value-for-parameter
            clusters.delete().where(clusters.c.id.in_(created_cluster_ids))
        )


async def test_get_default_cluster_entrypoint(
    clusters_config: None, async_client: httpx.AsyncClient
):
    # This test checks that the default cluster is accessible
    # the default cluster is the osparc internal cluster available through a dask-scheduler
    response = await async_client.get("/v2/clusters/default")
    assert response.status_code == status.HTTP_200_OK
    default_cluster_out = ClusterOut.parse_obj(response.json())
    response = await async_client.get(f"/v2/clusters/{0}")
    assert response.status_code == status.HTTP_200_OK
    assert default_cluster_out == ClusterOut.parse_obj(response.json())


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
                        f"cluster {cluster=} has now {len(cluster.scheduler_info.get('workers', []))}"
                    )
                    assert len(cluster.scheduler_info.get("workers", 0)) == 10

            async with cluster.get_client() as client:
                print(f"--> created new client {client=}, submitting a job")
                res = await client.submit(lambda x: x + 1, 1)  # type: ignore
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


@pytest.fixture
async def dask_gateway(
    local_dask_gateway_server: DaskGatewayServer,
) -> Gateway:
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
        return gateway


@pytest.fixture
async def dask_gateway_cluster(dask_gateway: Gateway) -> AsyncIterator[GatewayCluster]:
    async with dask_gateway.new_cluster() as cluster:
        yield cluster


@pytest.fixture
async def dask_gateway_cluster_client(
    dask_gateway_cluster: GatewayCluster,
) -> AsyncIterator[DaskClient]:
    async with dask_gateway_cluster.get_client() as client:
        yield client


async def _get_cluster_out(
    async_client: httpx.AsyncClient, cluster_id: NonNegativeInt
) -> ClusterOut:
    response = await async_client.get(f"/v2/clusters/{cluster_id}")
    assert response.status_code == status.HTTP_200_OK
    print(f"<-- received cluster details response {response=}")
    cluster_out = ClusterOut.parse_obj(response.json())
    assert cluster_out
    print(f"<-- received cluster details {cluster_out=}")
    assert cluster_out.scheduler, "the cluster's scheduler is not started!"
    return cluster_out


async def test_get_cluster_entrypoint(
    clusters_config: None,
    async_client: httpx.AsyncClient,
    local_dask_gateway_server: DaskGatewayServer,
    cluster: Callable[..., Cluster],
    dask_gateway_cluster: GatewayCluster,
    dask_gateway_cluster_client: DaskClient,
):
    # define the cluster in the DB
    some_cluster = cluster(
        endpoint=local_dask_gateway_server.address,
        authentication=SimpleAuthentication(
            username="pytest_user", password=local_dask_gateway_server.password
        ).dict(by_alias=True),
    )
    # in its present state, the cluster should have no workers
    cluster_out = await _get_cluster_out(async_client, some_cluster.id)
    assert not cluster_out.scheduler.workers, "the cluster should not have any worker!"

    # now let's scale the cluster
    _NUM_WORKERS = 1
    await dask_gateway_cluster.scale(_NUM_WORKERS)
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(60), wait=wait_fixed(1)
    ):
        with attempt:
            cluster_out = await _get_cluster_out(async_client, some_cluster.id)
            assert cluster_out.scheduler.workers, "the cluster has no workers!"
            assert (
                len(cluster_out.scheduler.workers) == _NUM_WORKERS
            ), f"the cluster is missing {_NUM_WORKERS}, currently has {len(cluster_out.scheduler.workers)}"
            print(
                f"cluster now has its {_NUM_WORKERS}, after {json.dumps(attempt.retry_state.retry_object.statistics)}"
            )
    print(f"!!> cluster dashboard link: {dask_gateway_cluster.dashboard_link}")

    # let's start some computation
    _TASK_SLEEP_TIME = 5

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
            cluster_out = await _get_cluster_out(async_client, some_cluster.id)
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.executing
                == 1
            ), "worker is not executing the task"
            print(
                f"!!> cluster metrics: {next(iter(cluster_out.scheduler.workers.values())).metrics=}"
            )
    # let's wait for the result
    result = task.result(timeout=_TASK_SLEEP_TIME + 5)
    assert result
    assert await result == True
    # wait for the computation to effectively stop
    async for attempt in AsyncRetrying(
        reraise=True, stop=stop_after_delay(20), wait=wait_fixed(1)
    ):
        with attempt:
            cluster_out = await _get_cluster_out(async_client, some_cluster.id)
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.executing
                == 0
            ), "worker is still executing the task"
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.in_memory
                == 1
            ), "worker did not keep the result in memory"
            assert (
                next(iter(cluster_out.scheduler.workers.values())).metrics.cpu == 0
            ), "worker did not keep the result in memory"
            print(
                f"!!> cluster metrics: {next(iter(cluster_out.scheduler.workers.values())).metrics=}"
            )

    # since the task is completed the worker should have stopped executing
    cluster_out = await _get_cluster_out(async_client, some_cluster.id)
    worker_data = next(iter(cluster_out.scheduler.workers.values()))
    assert worker_data.metrics.executing == 0
    # in dask, the task remains in memory until the result is deleted
    assert worker_data.metrics.in_memory == 1
