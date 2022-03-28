import logging
import os
import socket
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Final, Optional, Union

import dask_gateway
import distributed
import httpx
from aiohttp import ClientConnectionError, ClientResponseError
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from models_library.clusters import (
    ClusterAuthentication,
    JupyterHubTokenAuthentication,
    KerberosAuthentication,
    NoAuthentication,
    SimpleAuthentication,
)
from pydantic import AnyUrl

from ..core.errors import (
    ConfigurationError,
    DaskClientRequestError,
    DaskClusterError,
    DaskGatewayServerError,
    SchedulerError,
)

DaskGatewayAuths = Union[
    dask_gateway.BasicAuth, dask_gateway.KerberosAuth, dask_gateway.JupyterHubAuth
]


@dataclass
class TaskHandlers:
    task_change_handler: Callable[[str], Awaitable[None]]
    task_progress_handler: Callable[[str], Awaitable[None]]
    task_log_handler: Callable[[str], Awaitable[None]]


logger = logging.getLogger(__name__)


@dataclass
class DaskSubSystem:
    client: distributed.Client
    scheduler_id: str
    gateway: Optional[dask_gateway.Gateway]
    gateway_cluster: Optional[dask_gateway.GatewayCluster]
    state_sub: distributed.Sub = field(init=False)
    progress_sub: distributed.Sub = field(init=False)
    logs_sub: distributed.Sub = field(init=False)

    def __post_init__(self) -> None:
        self.state_sub = distributed.Sub(
            TaskStateEvent.topic_name(), client=self.client
        )
        self.progress_sub = distributed.Sub(
            TaskProgressEvent.topic_name(), client=self.client
        )
        self.logs_sub = distributed.Sub(TaskLogEvent.topic_name(), client=self.client)

    async def close(self):
        # NOTE: if the Sub are deleted before closing the connection,
        # then the dask-scheduler goes in a bad state [https://github.com/dask/distributed/issues/3276]
        # closing the client appears to fix the issue and the dask-scheduler remains happy
        if self.client:
            await self.client.close()  # type: ignore
        if self.gateway_cluster:
            await self.gateway_cluster.close()  # type: ignore
        if self.gateway:
            await self.gateway.close()  # type: ignore


async def _connect_to_dask_scheduler(endpoint: AnyUrl) -> DaskSubSystem:
    try:
        client = await distributed.Client(  # type: ignore
            f"{endpoint}",
            asynchronous=True,
            name=f"director-v2_{socket.gethostname()}_{os.getpid()}",
        )
        return DaskSubSystem(
            client=client,
            scheduler_id=client.scheduler_info()["id"],
            gateway=None,
            gateway_cluster=None,
        )
    except (TypeError) as exc:
        raise ConfigurationError(
            f"Scheduler has invalid configuration: {endpoint=}"
        ) from exc


async def _connect_with_gateway_and_create_cluster(
    endpoint: AnyUrl, auth_params: ClusterAuthentication
) -> DaskSubSystem:
    try:
        logger.debug(
            "connecting with gateway at %s with %s", f"{endpoint!r}", f"{auth_params=}"
        )
        gateway_auth = await get_gateway_auth_from_params(auth_params)
        gateway = dask_gateway.Gateway(
            address=f"{endpoint}", auth=gateway_auth, asynchronous=True
        )

        try:
            # if there is already a cluster that means we can re-connect to it,
            # and IT SHALL BE the first in the list
            cluster_reports_list = await gateway.list_clusters()
            logger.debug(
                "current clusters on the gateway: %s", f"{cluster_reports_list=}"
            )
            cluster = None
            if cluster_reports_list:
                assert (
                    len(cluster_reports_list) == 1
                ), "More than 1 cluster at this location, that is unexpected!!"  # nosec
                cluster = await gateway.connect(
                    cluster_reports_list[0].name, shutdown_on_close=False
                )
                logger.debug("connected to %s", f"{cluster=}")
            else:
                cluster = await gateway.new_cluster(shutdown_on_close=False)
                logger.debug("created %s", f"{cluster=}")
            assert cluster  # nosec
            logger.info("Cluster dashboard available: %s", cluster.dashboard_link)
            # NOTE: we scale to 1 worker as they are global
            await cluster.adapt(active=True)
            client = await cluster.get_client()  # type: ignore
            assert client  # nosec
            return DaskSubSystem(
                client=client,
                scheduler_id=client.scheduler_info()["id"],
                gateway=gateway,
                gateway_cluster=cluster,
            )
        except Exception as exc:
            # cleanup
            with suppress(Exception):
                await gateway.close()  # type: ignore
            raise exc

    except (TypeError) as exc:
        raise ConfigurationError(
            f"Cluster has invalid configuration: {endpoint=}, {auth_params=}"
        ) from exc
    except (ValueError) as exc:
        # this is when a 404=NotFound,422=MalformedData comes up
        raise DaskClientRequestError(endpoint=endpoint, error=exc) from exc
    except (dask_gateway.GatewayClusterError) as exc:
        # this is when a 409=Conflict/Cannot complete request comes up
        raise DaskClusterError(endpoint=endpoint, error=exc) from exc
    except (dask_gateway.GatewayServerError) as exc:
        # this is when a 500 comes up
        raise DaskGatewayServerError(endpoint=endpoint, error=exc) from exc


def _is_internal_scheduler(authentication: ClusterAuthentication) -> bool:
    return isinstance(authentication, NoAuthentication)


async def create_internal_client_based_on_auth(
    endpoint: AnyUrl, authentication: ClusterAuthentication
) -> DaskSubSystem:
    if _is_internal_scheduler(authentication):
        # if no auth then we go for a standard scheduler connection
        return await _connect_to_dask_scheduler(endpoint)
    # we do have some auth, so it is going through a gateway
    return await _connect_with_gateway_and_create_cluster(endpoint, authentication)


async def get_gateway_auth_from_params(
    auth_params: ClusterAuthentication,
) -> DaskGatewayAuths:
    try:
        if isinstance(auth_params, SimpleAuthentication):
            return dask_gateway.BasicAuth(
                username=auth_params.username,
                password=auth_params.password.get_secret_value(),
            )
        if isinstance(auth_params, KerberosAuthentication):
            return dask_gateway.KerberosAuth()
        if isinstance(auth_params, JupyterHubTokenAuthentication):
            return dask_gateway.JupyterHubAuth(auth_params.api_token)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"Cluster has invalid configuration: {auth_params}"
        ) from exc

    raise ConfigurationError(f"Cluster has invalid configuration: {auth_params=}")


_PING_TIMEOUT_S: Final[int] = 5


async def test_scheduler_endpoint(
    endpoint: AnyUrl, authentication: ClusterAuthentication
) -> None:
    """This method will try to connect to a gateway endpoint and raise a ConfigurationError in case of problem

    :raises ConfigurationError: contians some information as to why the connection failed
    """
    try:
        if _is_internal_scheduler(authentication):
            async with distributed.Client(
                address=endpoint, timeout=_PING_TIMEOUT_S, asynchronous=True
            ) as dask_client:
                if not dask_client.status == "running":
                    raise SchedulerError("internal scheduler is not running!")

        else:
            gateway_auth = await get_gateway_auth_from_params(authentication)
            async with dask_gateway.Gateway(
                address=f"{endpoint}", auth=gateway_auth, asynchronous=True
            ) as gateway:
                # this does not yet create any connection to the underlying gateway.
                # since using a fct from dask gateway is going to timeout after a long time
                # we bypass the pinging by calling in ourselves with a short timeout
                async with httpx.AsyncClient(
                    transport=httpx.AsyncHTTPTransport(retries=2)
                ) as httpx_client:
                    # try to get something the api shall return fast
                    response = await httpx_client.get(
                        f"{endpoint}/api/version", timeout=_PING_TIMEOUT_S
                    )
                    response.raise_for_status()
                    # now we try to list the clusters to check the gateway responds in a sensible way
                    await gateway.list_clusters()

                logger.debug("Pinging %s, succeeded", f"{endpoint=}")
    except (
        dask_gateway.GatewayServerError,
        ClientConnectionError,
        ClientResponseError,
        httpx.HTTPError,
        SchedulerError,
    ) as exc:
        logger.debug("Pinging %s, failed: %s", f"{endpoint=}", f"{exc=!r}")
        raise ConfigurationError(
            f"Could not connect to cluster in {endpoint}: error: {exc}"
        ) from exc
