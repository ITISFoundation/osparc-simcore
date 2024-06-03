import contextlib
from collections.abc import AsyncGenerator, Awaitable, Coroutine
from typing import Any

import distributed
import rich

from .constants import SSH_USER_NAME, TASK_CANCEL_EVENT_NAME_TEMPLATE
from .models import AppState, ComputationalCluster, TaskId


def _wrap_dask_async_call(called_fct) -> Awaitable[Any]:
    assert isinstance(called_fct, Coroutine)
    return called_fct


@contextlib.asynccontextmanager
async def dask_client(
    state: AppState, ip_address: str
) -> AsyncGenerator[distributed.Client, None]:
    security = distributed.Security()
    assert state.deploy_config
    dask_certificates = state.deploy_config / "assets" / "dask-certificates"
    if dask_certificates.exists():
        security = distributed.Security(
            tls_ca_file=f"{dask_certificates / 'dask-cert.pem'}",
            tls_client_cert=f"{dask_certificates / 'dask-cert.pem'}",
            tls_client_key=f"{dask_certificates / 'dask-key.pem'}",
            require_encryption=True,
        )
    try:
        assert state.ssh_key_path  # nosec
        with ssh_tunnel(
            ssh_host=_BASTION_HOST,
            username=SSH_USER_NAME,
            private_key_path=state.ssh_key_path,
            remote_bind_host=ip_address,
            remote_bind_port=_SCHEDULER_PORT,
        ) as tunnel:
            assert tunnel  # nosec
            host, port = tunnel.local_bind_address
            forward_url = f"tls://{host}:{port}"
            async with distributed.Client(
                forward_url,
                security=security,
                timeout="5",
                asynchronous=True,
            ) as client:
                yield client
    finally:
        pass


async def remove_job_from_scheduler(
    state: AppState,
    cluster: ComputationalCluster,
    task_id: TaskId,
) -> None:
    async with dask_client(
        state,
        cluster.primary.ec2_instance.private_dns_name,
    ) as client:
        await _wrap_dask_async_call(client.unpublish_dataset(task_id))
        rich.print(f"unpublished {task_id} from scheduler")


async def trigger_job_cancellation_in_scheduler(
    state: AppState,
    cluster: ComputationalCluster,
    task_id: TaskId,
) -> None:
    async with dask_client(
        state, cluster.primary.ec2_instance.private_dns_name
    ) as client:
        task_future = distributed.Future(task_id)
        cancel_event = distributed.Event(
            name=TASK_CANCEL_EVENT_NAME_TEMPLATE.format(task_future.key),
            client=client,
        )
        await _wrap_dask_async_call(cancel_event.set())
        await _wrap_dask_async_call(task_future.cancel())
        rich.print(f"cancelled {task_id} in scheduler/workers")
