import logging
import os
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final

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
    TLSAuthentication,
)
from pydantic import AnyUrl

from ..core.errors import ComputationalSchedulerError, ConfigurationError
from .dask import wrap_client_async_routine


@dataclass
class TaskHandlers:
    task_progress_handler: Callable[[str], Awaitable[None]]
    task_log_handler: Callable[[str], Awaitable[None]]


logger = logging.getLogger(__name__)


@dataclass
class DaskSubSystem:
    client: distributed.Client
    scheduler_id: str
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
        return DaskSubSystem(client=client, scheduler_id=client.scheduler_info()["id"])
    except TypeError as exc:
        msg = f"Scheduler has invalid configuration: {endpoint=}"
        raise ConfigurationError(msg=msg) from exc


async def create_internal_client_based_on_auth(
    endpoint: AnyUrl, authentication: ClusterAuthentication
) -> DaskSubSystem:
    return await _connect_to_dask_scheduler(endpoint, authentication)  # type: ignore[arg-type] # _is_dask_scheduler checks already that it is a valid type


_PING_TIMEOUT_S: Final[int] = 5
_DASK_SCHEDULER_RUNNING_STATE: Final[str] = "running"


async def test_scheduler_endpoint(endpoint: AnyUrl) -> None:
    """This method will try to connect to a scheduler endpoint and raise a ConfigurationError in case of problem

    :raises ConfigurationError: contians some information as to why the connection failed
    """
    try:
        async with distributed.Client(
            address=f"{endpoint}", timeout=f"{_PING_TIMEOUT_S}", asynchronous=True
        ) as dask_client:
            if dask_client.status != _DASK_SCHEDULER_RUNNING_STATE:
                msg = "internal scheduler is not running!"
                raise ComputationalSchedulerError(msg=msg)  # noqa: TRY301

    except (
        ClientConnectionError,
        ClientResponseError,
        httpx.HTTPError,
        ComputationalSchedulerError,
    ) as exc:
        logger.debug("Pinging %s, failed: %s", f"{endpoint=}", f"{exc=!r}")
        msg = f"Could not connect to cluster in {endpoint}: error: {exc}"
        raise ConfigurationError(msg=msg) from exc
