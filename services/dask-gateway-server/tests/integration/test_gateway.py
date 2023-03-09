# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
import traitlets
import traitlets.config
from _host_helpers import get_this_computer_ip
from _pytest.fixtures import FixtureRequest
from _pytest.monkeypatch import MonkeyPatch
from dask_gateway_server.app import DaskGateway
from faker import Faker
from osparc_gateway_server.backend.osparc import OsparcBackend


@pytest.fixture(
    params=[
        "itisfoundation/dask-sidecar:master-github-latest",
    ]
)
def minimal_config(
    docker_swarm,
    monkeypatch: MonkeyPatch,
    faker: Faker,
    request: FixtureRequest,
):
    monkeypatch.setenv("GATEWAY_WORKERS_NETWORK", faker.pystr())
    monkeypatch.setenv("GATEWAY_SERVER_NAME", get_this_computer_ip())
    monkeypatch.setenv("COMPUTATIONAL_SIDECAR_VOLUME_NAME", faker.pystr())
    monkeypatch.setenv(
        "COMPUTATIONAL_SIDECAR_IMAGE",
        request.param,  # type: ignore
    )
    monkeypatch.setenv("COMPUTATIONAL_SIDECAR_LOG_LEVEL", "DEBUG")


async def test_gateway_configuration_through_env_variables(
    minimal_config, monkeypatch, faker: Faker
):
    cluster_start_timeout = faker.pyfloat()
    monkeypatch.setenv("GATEWAY_CLUSTER_START_TIMEOUT", f"{cluster_start_timeout}")
    worker_start_timeout = faker.pyfloat()
    monkeypatch.setenv("GATEWAY_WORKER_START_TIMEOUT", f"{worker_start_timeout}")
    c = traitlets.config.Config()
    c.DaskGateway.backend_class = OsparcBackend  # type: ignore
    dask_gateway_server = DaskGateway(config=c)
    dask_gateway_server.initialize([])  # that is a shitty one!
    print("--> local dask gateway server initialized")
    await dask_gateway_server.setup()
    await dask_gateway_server.backend.proxy._proxy_contacted  # pylint: disable=protected-access
    print("--> local dask gateway server setup completed")

    assert dask_gateway_server.backend.cluster_start_timeout == cluster_start_timeout
    assert dask_gateway_server.backend.worker_start_timeout == worker_start_timeout

    print("<-- local dask gateway server switching off...")
    await dask_gateway_server.cleanup()
    print("...done")
