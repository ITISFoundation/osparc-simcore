import asyncio
import logging
from typing import Final

import dask_gateway
from aiohttp.client_exceptions import ClientError
from pydantic import AnyUrl, SecretStr

_logger = logging.getLogger(__name__)

_PING_USERNAME: Final[str] = "osparc-cluster"


async def ping_gateway(*, url: AnyUrl, password: SecretStr) -> bool:
    basic_auth = dask_gateway.BasicAuth(
        username=_PING_USERNAME, password=password.get_secret_value()
    )
    try:
        async with dask_gateway.Gateway(
            address=f"{url}",
            auth=basic_auth,
            asynchronous=True,
        ) as gateway:
            cluster_reports = await asyncio.wait_for(gateway.list_clusters(), timeout=5)
        _logger.info("found %s clusters", len(cluster_reports))
        return True
    except asyncio.TimeoutError:
        _logger.debug("gateway ping timed-out, it is still starting...")
    except ClientError:
        # this could happen if the gateway is not properly started, but it should not last
        # unless the wrong password is used.
        _logger.info("dask-gateway is not reachable", exc_info=True)

    return False


async def is_gateway_busy(*, url: AnyUrl, user: str, password: SecretStr) -> bool:
    basic_auth = dask_gateway.BasicAuth(
        username=user, password=password.get_secret_value()
    )
    async with dask_gateway.Gateway(
        address=f"{url}",
        auth=basic_auth,
        asynchronous=True,
    ) as gateway:
        cluster_reports = await asyncio.wait_for(gateway.list_clusters(), timeout=5)
        if not cluster_reports:
            _logger.info("no cluster in gateway, nothing going on")
            return False
        assert len(cluster_reports) == 1  # nosec
        async with gateway.connect(
            cluster_reports[0].name, shutdown_on_close=False
        ) as dask_cluster, dask_cluster.get_client() as client:
            datasets_on_scheduler = await client.list_datasets()  # type: ignore
            _logger.info(
                "cluster currently has %s datasets, it is %s",
                len(datasets_on_scheduler),
                "BUSY" if len(datasets_on_scheduler) > 0 else "NOT BUSY",
            )
            currently_processing = await client.processing()  # type: ignore
            return bool(datasets_on_scheduler or currently_processing)
