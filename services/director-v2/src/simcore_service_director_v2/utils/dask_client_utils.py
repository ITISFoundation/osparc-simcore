import logging
import os
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import distributed
from models_library.clusters import ClusterAuthentication, TLSAuthentication
from pydantic import AnyUrl

from ..core.errors import ConfigurationError
from .dask import wrap_client_async_routine


@dataclass
class TaskHandlers:
    task_progress_handler: Callable[[str], Awaitable[None]]


logger = logging.getLogger(__name__)


@dataclass
class DaskSubSystem:
    client: distributed.Client
    scheduler_id: str

    async def close(self) -> None:
        # NOTE: if the Sub are deleted before closing the connection,
        # then the dask-scheduler goes in a bad state [https://github.com/dask/distributed/issues/3276]
        # closing the client appears to fix the issue and the dask-scheduler remains happy
        if self.client:
            await wrap_client_async_routine(self.client.close())


async def connect_to_dask_scheduler(
    endpoint: AnyUrl, authentication: ClusterAuthentication
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
