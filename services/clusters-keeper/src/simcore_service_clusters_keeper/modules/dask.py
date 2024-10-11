import logging
from collections.abc import Coroutine
from typing import Any, Final

import distributed
from models_library.clusters import InternalClusterAuthentication, TLSAuthentication
from pydantic import AnyUrl

_logger = logging.getLogger(__name__)


async def _wrap_client_async_routine(
    client_coroutine: Coroutine[Any, Any, Any] | Any | None
) -> Any:
    """Dask async behavior does not go well with Pylance as it returns
    a union of types. this wrapper makes both mypy and pylance happy"""
    assert client_coroutine  # nosec
    return await client_coroutine


_CONNECTION_TIMEOUT: Final[str] = "5"


async def ping_scheduler(
    url: AnyUrl, authentication: InternalClusterAuthentication
) -> bool:
    try:
        security = distributed.Security()
        if isinstance(authentication, TLSAuthentication):
            security = distributed.Security(
                tls_ca_file=f"{authentication.tls_ca_file}",
                tls_client_cert=f"{authentication.tls_client_cert}",
                tls_client_key=f"{authentication.tls_client_key}",
                require_encryption=True,
            )
        async with distributed.Client(
            f"{url}", asynchronous=True, timeout=_CONNECTION_TIMEOUT, security=security
        ):
            ...
        return True
    except OSError:
        _logger.info(
            "osparc-dask-scheduler %s ping timed-out, the machine is likely still starting/hanged or broken...",
            url,
        )

    return False


async def is_scheduler_busy(
    url: AnyUrl, authentication: InternalClusterAuthentication
) -> bool:
    security = distributed.Security()
    if isinstance(authentication, TLSAuthentication):
        security = distributed.Security(
            tls_ca_file=f"{authentication.tls_ca_file}",
            tls_client_cert=f"{authentication.tls_client_cert}",
            tls_client_key=f"{authentication.tls_client_key}",
            require_encryption=True,
        )
    async with distributed.Client(
        f"{url}", asynchronous=True, timeout=_CONNECTION_TIMEOUT, security=security
    ) as client:
        datasets_on_scheduler = await _wrap_client_async_routine(client.list_datasets())
        _logger.info("cluster currently has %s datasets", len(datasets_on_scheduler))
        num_processing_tasks = 0
        if worker_to_processing_tasks := await _wrap_client_async_routine(
            client.processing()
        ):
            _logger.info(
                "cluster current workers: %s", worker_to_processing_tasks.keys()
            )
            num_processing_tasks = sum(
                len(tasks) for tasks in worker_to_processing_tasks.values()
            )
            _logger.info("cluster currently processes %s tasks", num_processing_tasks)

        return bool(datasets_on_scheduler or num_processing_tasks)
