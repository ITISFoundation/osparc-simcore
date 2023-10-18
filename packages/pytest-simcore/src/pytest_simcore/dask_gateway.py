# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from collections.abc import Callable
from typing import AsyncIterator, NamedTuple

import pytest
import traitlets.config
from dask_gateway import Gateway, GatewayCluster, auth
from dask_gateway_server.app import DaskGateway
from dask_gateway_server.backends.local import UnsafeLocalBackend
from distributed import Client
from faker import Faker


@pytest.fixture
def local_dask_gateway_server_config(
    unused_tcp_port_factory: Callable,
) -> traitlets.config.Config:
    c = traitlets.config.Config()
    assert isinstance(c.DaskGateway, traitlets.config.Config)
    assert isinstance(c.ClusterConfig, traitlets.config.Config)
    assert isinstance(c.Proxy, traitlets.config.Config)
    assert isinstance(c.SimpleAuthenticator, traitlets.config.Config)
    c.DaskGateway.backend_class = UnsafeLocalBackend
    c.DaskGateway.address = f"127.0.0.1:{unused_tcp_port_factory()}"
    c.Proxy.address = f"127.0.0.1:{unused_tcp_port_factory()}"
    c.DaskGateway.authenticator_class = "dask_gateway_server.auth.SimpleAuthenticator"
    c.SimpleAuthenticator.password = "qweqwe"  # noqa: S105
    c.ClusterConfig.worker_cmd = [
        "dask-worker",
        "--resources",
        f"CPU=12,GPU=1,RAM={16e9}",
    ]
    # NOTE: This must be set such that the local unsafe backend creates a worker with enough cores/memory
    c.ClusterConfig.worker_cores = 12
    c.ClusterConfig.worker_memory = "16G"
    c.ClusterConfig.cluster_max_workers = 3

    c.DaskGateway.log_level = "DEBUG"
    return c


class DaskGatewayServer(NamedTuple):
    address: str
    proxy_address: str
    password: str
    server: DaskGateway


@pytest.fixture
async def local_dask_gateway_server(
    local_dask_gateway_server_config: traitlets.config.Config,
) -> AsyncIterator[DaskGatewayServer]:
    print("--> creating local dask gateway server")
    dask_gateway_server = DaskGateway(config=local_dask_gateway_server_config)
    dask_gateway_server.initialize([])  # that is a shitty one!
    print("--> local dask gateway server initialized")
    await dask_gateway_server.setup()
    await dask_gateway_server.backend.proxy._proxy_contacted  # pylint: disable=protected-access

    print("--> local dask gateway server setup completed")
    yield DaskGatewayServer(
        f"http://{dask_gateway_server.backend.proxy.address}",
        f"gateway://{dask_gateway_server.backend.proxy.tcp_address}",
        local_dask_gateway_server_config.SimpleAuthenticator.password,  # type: ignore
        dask_gateway_server,
    )
    print("--> local dask gateway server switching off...")
    await dask_gateway_server.cleanup()
    print("...done")


@pytest.fixture
def gateway_username(faker: Faker) -> str:
    return faker.user_name()


@pytest.fixture
def gateway_auth(
    local_dask_gateway_server: DaskGatewayServer, gateway_username: str
) -> auth.BasicAuth:
    return auth.BasicAuth(gateway_username, local_dask_gateway_server.password)


@pytest.fixture
async def dask_gateway(
    local_dask_gateway_server: DaskGatewayServer, gateway_auth: auth.BasicAuth
) -> Gateway:
    async with Gateway(
        local_dask_gateway_server.address,
        local_dask_gateway_server.proxy_address,
        asynchronous=True,
        auth=gateway_auth,
    ) as gateway:
        print(
            f"--> {gateway=} created, with {gateway_auth.username=}/{gateway_auth.password=}"
        )
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
) -> AsyncIterator[Client]:
    async with dask_gateway_cluster.get_client() as client:
        yield client
