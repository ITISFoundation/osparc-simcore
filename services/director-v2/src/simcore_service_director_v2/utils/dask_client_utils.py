import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Union

import dask_gateway
import distributed
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
        client = await distributed.Client(
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
        gateway_auth = await get_gateway_auth_from_params(auth_params)
        gateway = dask_gateway.Gateway(
            address=f"{endpoint}", auth=gateway_auth, asynchronous=True
        )
        # if there is already a cluster that means we can re-connect to it,
        # and IT SHALL BE the first in the list
        cluster_reports_list = await gateway.list_clusters()
        cluster = None
        if cluster_reports_list:
            assert (
                len(cluster_reports_list) == 1
            ), "More than 1 cluster at this location, that is unexpected!!"  # nosec
            cluster = await gateway.connect(
                cluster_reports_list[0].name, shutdown_on_close=False
            )
        else:
            cluster = await gateway.new_cluster(shutdown_on_close=False)
        assert cluster  # nosec
        logger.info("Cluster dashboard available: %s", cluster.dashboard_link)
        # NOTE: we scale to 1 worker as they are global
        await cluster.adapt(active=True)
        client = await cluster.get_client()
        assert client  # nosec
        return DaskSubSystem(
            client=client,
            scheduler_id=client.scheduler_info()["id"],
            gateway=gateway,
            gateway_cluster=cluster,
        )
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


async def create_internal_client_based_on_auth(
    endpoint: AnyUrl, authentication: ClusterAuthentication
) -> DaskSubSystem:
    if isinstance(authentication, NoAuthentication):
        # if no auth then we go for a standard scheduler connection
        return await _connect_to_dask_scheduler(endpoint)
    # we do have some auth, so it is going through a gateway
    return await _connect_with_gateway_and_create_cluster(endpoint, authentication)


async def get_gateway_auth_from_params(
    auth_params: ClusterAuthentication,
) -> DaskGatewayAuths:
    try:
        if isinstance(auth_params, SimpleAuthentication):
            return dask_gateway.BasicAuth(**auth_params.dict(exclude={"type"}))
        if isinstance(auth_params, KerberosAuthentication):
            return dask_gateway.KerberosAuth()
        if isinstance(auth_params, JupyterHubTokenAuthentication):
            return dask_gateway.JupyterHubAuth(auth_params.api_token)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"Cluster has invalid configuration: {auth_params}"
        ) from exc

    raise ConfigurationError(f"Cluster has invalid configuration: {auth_params=}")
