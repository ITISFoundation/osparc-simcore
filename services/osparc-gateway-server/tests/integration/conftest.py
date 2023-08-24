# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import asyncio
import json
from typing import Any, AsyncIterator, Awaitable, Callable

import aiodocker
import dask_gateway
import pytest
import traitlets
import traitlets.config
from _dask_helpers import DaskGatewayServer
from dask_gateway_server.app import DaskGateway
from faker import Faker
from osparc_gateway_server.backend.osparc import OsparcBackend
from osparc_gateway_server.backend.utils import (
    OSPARC_SCHEDULER_API_PORT,
    OSPARC_SCHEDULER_DASHBOARD_PORT,
)
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from tenacity._asyncio import AsyncRetrying
from tenacity.wait import wait_fixed


@pytest.fixture
async def docker_volume(
    async_docker_client: aiodocker.Docker,
) -> AsyncIterator[Callable[[str], Awaitable[dict[str, Any]]]]:
    volumes = []

    async def _volume_creator(name: str) -> dict[str, Any]:
        volume = await async_docker_client.volumes.create(config={"Name": name})
        assert volume
        print(f"--> created {volume=}")
        volumes.append(volume)
        return await volume.show()

    yield _volume_creator

    # cleanup
    async def _wait_for_volume_deletion(volume: aiodocker.docker.DockerVolume):
        inspected_volume = await volume.show()
        async for attempt in AsyncRetrying(reraise=True, wait=wait_fixed(1)):
            with attempt:
                print(f"<-- deleting volume '{inspected_volume['Name']}'...")
                await volume.delete()
            print(f"<-- volume '{inspected_volume['Name']}' deleted")

    await asyncio.gather(*[_wait_for_volume_deletion(v) for v in volumes])


@pytest.fixture
def gateway_password(faker: Faker) -> str:
    return faker.password()


def _convert_to_dict(c: traitlets.config.Config | dict) -> dict[str, Any]:
    converted_dict = {}
    for x, y in c.items():
        if isinstance(y, (dict, traitlets.config.Config)):
            converted_dict[x] = _convert_to_dict(y)
        else:
            converted_dict[x] = f"{y}"
    return converted_dict


@pytest.fixture
def mock_scheduler_cmd_modifications(mocker):
    """This mock is necessary since:
    If the osparc-gateway-server is running in the host then:
    - dask-scheduler must start with "" for --host, so the dask-scheduler defines its IP as being in docker_gw_bridge (172.18.0.X), accessible from the host
    When the osparc-gateway-server is running as a docker container, then the --host must be set
    as "cluster_X_scheduler" since this is the hostname of the container and resolves into the dask-gateway network
    """
    mocker.patch(
        "osparc_gateway_server.backend.osparc.get_osparc_scheduler_cmd_modifications",
        autospec=True,
        return_value={
            "--dashboard-address": f":{OSPARC_SCHEDULER_DASHBOARD_PORT}",
            "--port": f"{OSPARC_SCHEDULER_API_PORT}",
        },
    )


@pytest.fixture
async def local_dask_gateway_server(
    mock_scheduler_cmd_modifications,
    minimal_config: None,
    gateway_password: str,
) -> AsyncIterator[DaskGatewayServer]:
    """this code is more or less copy/pasted from dask-gateway repo"""
    c = traitlets.config.Config()
    c.DaskGateway.backend_class = OsparcBackend  # type: ignore
    c.DaskGateway.address = "127.0.0.1:0"  # type: ignore
    c.DaskGateway.log_level = "DEBUG"  # type: ignore
    c.Proxy.address = f"{get_localhost_ip()}:0"  # type: ignore
    c.DaskGateway.authenticator_class = "dask_gateway_server.auth.SimpleAuthenticator"  # type: ignore
    c.SimpleAuthenticator.password = gateway_password  # type: ignore
    print(f"--> local dask gateway config: {json.dumps(_convert_to_dict(c), indent=2)}")
    dask_gateway_server = DaskGateway(config=c)
    dask_gateway_server.initialize([])  # that is a shitty one!
    print("--> local dask gateway server initialized")
    await dask_gateway_server.setup()
    await dask_gateway_server.backend.proxy._proxy_contacted  # pylint: disable=protected-access
    print("--> local dask gateway server setup completed")
    yield DaskGatewayServer(
        f"http://{dask_gateway_server.backend.proxy.address}",
        f"gateway://{dask_gateway_server.backend.proxy.tcp_address}",
        c.SimpleAuthenticator.password,  # type: ignore
        dask_gateway_server,
    )
    print("<-- local dask gateway server switching off...")
    await dask_gateway_server.cleanup()
    print("...done")


@pytest.fixture
async def gateway_client(
    local_dask_gateway_server: DaskGatewayServer,
) -> AsyncIterator[dask_gateway.Gateway]:
    async with dask_gateway.Gateway(
        local_dask_gateway_server.address,
        local_dask_gateway_server.proxy_address,
        asynchronous=True,
        auth=dask_gateway.BasicAuth(
            username="pytest_user", password=local_dask_gateway_server.password
        ),
    ) as gateway:
        assert gateway
        print(f"--> {gateway} created")
        cluster_options = await gateway.cluster_options()
        gateway_versions = await gateway.get_versions()
        clusters_list = await gateway.list_clusters()
        print(f"--> {gateway_versions}, {cluster_options}, {clusters_list}")
        for option in cluster_options.items():
            print(f"--> {option}")
        yield gateway
