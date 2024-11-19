import logging
import os
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Final, Union

import dask_gateway  # type: ignore[import-untyped]
import distributed
import httpx
from aiohttp import ClientConnectionError, ClientResponseError
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
)
from models_library.clusters import (
    ClusterAuthentication,
    InternalClusterAuthentication,
    JupyterHubTokenAuthentication,
    KerberosAuthentication,
    NoAuthentication,
    SimpleAuthentication,
    TLSAuthentication,
)
from pydantic import AnyUrl

from ..core.errors import (
    ComputationalSchedulerError,
    ConfigurationError,
    DaskClientRequestError,
    DaskClusterError,
    DaskGatewayServerError,
)
from .dask import check_maximize_workers, wrap_client_async_routine

DaskGatewayAuths = Union[
    dask_gateway.BasicAuth, dask_gateway.KerberosAuth, dask_gateway.JupyterHubAuth
]


@dataclass
class TaskHandlers:
    task_progress_handler: Callable[[str], Awaitable[None]]
    task_log_handler: Callable[[str], Awaitable[None]]


logger = logging.getLogger(__name__)


@dataclass
class DaskSubSystem:
    client: distributed.Client
    scheduler_id: str
    gateway: dask_gateway.Gateway | None
    gateway_cluster: dask_gateway.GatewayCluster | None
    progress_sub: distributed.Sub = field(init=False)
    logs_sub: distributed.Sub = field(init=False)

    def __post_init__(self) -> None:
        self.progress_sub = distributed.Sub(
            TaskProgressEvent.topic_name(), client=self.client
        )
        self.logs_sub = distributed.Sub(TaskLogEvent.topic_name(), client=self.client)

    async def close(self) -> None:
        # NOTE: if the Sub are deleted before closing the connection,
        # then the dask-scheduler goes in a bad state [https://github.com/dask/distributed/issues/3276]
        # closing the client appears to fix the issue and the dask-scheduler remains happy
        if self.client:
            await wrap_client_async_routine(self.client.close())
        if self.gateway_cluster:
            await wrap_client_async_routine(self.gateway_cluster.close())
        if self.gateway:
            await wrap_client_async_routine(self.gateway.close())


async def _connect_to_dask_scheduler(
    endpoint: AnyUrl, authentication: InternalClusterAuthentication
) -> DaskSubSystem:
    try:
        security = distributed.Security()
        if isinstance(authentication, TLSAuthentication):
            security = distributed.Security(
                tls_ca_file=f"{authentication.tls_ca_file}",
                tls_client_cert=f"{authentication.tls_client_cert}",
                tls_client_key=f"{authentication.tls_client_key}",
                require_encryption=True,
            )
        client = await distributed.Client(
            f"{endpoint}",
            asynchronous=True,
            name=f"director-v2_{socket.gethostname()}_{os.getpid()}",
            security=security,
        )
        return DaskSubSystem(
            client=client,
            scheduler_id=client.scheduler_info()["id"],
            gateway=None,
            gateway_cluster=None,
        )
    except TypeError as exc:
        msg = f"Scheduler has invalid configuration: {endpoint=}"
        raise ConfigurationError(msg=msg) from exc


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
            await check_maximize_workers(cluster)
            logger.info("Cluster workers maximized")
            client = await cluster.get_client()
            assert client  # nosec
            return DaskSubSystem(
                client=client,
                scheduler_id=client.scheduler_info()["id"],
                gateway=gateway,
                gateway_cluster=cluster,
            )
        except Exception:
            # cleanup
            with suppress(Exception):
                await wrap_client_async_routine(gateway.close())
            raise

    except TypeError as exc:
        msg = f"Cluster has invalid configuration: {endpoint=}, {auth_params=}"
        raise ConfigurationError(msg=msg) from exc
    except ValueError as exc:
        # this is when a 404=NotFound,422=MalformedData comes up
        raise DaskClientRequestError(endpoint=endpoint, error=exc) from exc
    except dask_gateway.GatewayClusterError as exc:
        # this is when a 409=Conflict/Cannot complete request comes up
        raise DaskClusterError(endpoint=endpoint, error=exc) from exc
    except dask_gateway.GatewayServerError as exc:
        # this is when a 500 comes up
        raise DaskGatewayServerError(endpoint=endpoint, error=exc) from exc


def _is_dask_scheduler(authentication: ClusterAuthentication) -> bool:
    return isinstance(authentication, NoAuthentication | TLSAuthentication)


async def create_internal_client_based_on_auth(
    endpoint: AnyUrl, authentication: ClusterAuthentication
) -> DaskSubSystem:
    if _is_dask_scheduler(authentication):
        # if no auth then we go for a standard scheduler connection
        return await _connect_to_dask_scheduler(endpoint, authentication)  # type: ignore[arg-type] # _is_dask_scheduler checks already that it is a valid type
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
        msg = f"Cluster has invalid configuration: {auth_params}"
        raise ConfigurationError(msg=msg) from exc

    msg = f"Cluster has invalid configuration: {auth_params=}"
    raise ConfigurationError(msg=msg)


_PING_TIMEOUT_S: Final[int] = 5
_DASK_SCHEDULER_RUNNING_STATE: Final[str] = "running"


async def test_scheduler_endpoint(
    endpoint: AnyUrl, authentication: ClusterAuthentication
) -> None:
    """This method will try to connect to a gateway endpoint and raise a ConfigurationError in case of problem

    :raises ConfigurationError: contians some information as to why the connection failed
    """
    try:
        if _is_dask_scheduler(authentication):
            async with distributed.Client(
                address=f"{endpoint}", timeout=f"{_PING_TIMEOUT_S}", asynchronous=True
            ) as dask_client:
                if dask_client.status != _DASK_SCHEDULER_RUNNING_STATE:
                    msg = "internal scheduler is not running!"
                    raise ComputationalSchedulerError(msg=msg)

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
        ComputationalSchedulerError,
    ) as exc:
        logger.debug("Pinging %s, failed: %s", f"{endpoint=}", f"{exc=!r}")
        msg = f"Could not connect to cluster in {endpoint}: error: {exc}"
        raise ConfigurationError(msg=msg) from exc
