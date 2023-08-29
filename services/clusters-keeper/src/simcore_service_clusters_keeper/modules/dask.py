import asyncio
import logging

import dask_gateway
from aiohttp.client_exceptions import ClientError
from pydantic import SecretStr

from ..models import EC2InstanceData

_logger = logging.getLogger(__name__)

_USERNAME = "anderegg@itis.swiss"


async def ping_gateway(
    ec2_instance: EC2InstanceData, gateway_password: SecretStr
) -> bool:
    basic_auth = dask_gateway.BasicAuth(
        username=_USERNAME, password=gateway_password.get_secret_value()
    )
    try:
        async with dask_gateway.Gateway(
            address=f"http://{ec2_instance.aws_public_ip}:8000",
            auth=basic_auth,
            asynchronous=True,
        ) as gateway:
            cluster_reports = await asyncio.wait_for(gateway.list_clusters(), timeout=5)
        _logger.info("found %s clusters", len(cluster_reports))
        return True
    except (ClientError, asyncio.TimeoutError):
        _logger.info("dask-gateway is unavailable", exc_info=True)

    return False


async def is_gateway_busy(
    ec2_instance: EC2InstanceData, gateway_password: SecretStr
) -> bool:
    basic_auth = dask_gateway.BasicAuth(
        username=_USERNAME, password=gateway_password.get_secret_value()
    )
    async with dask_gateway.Gateway(
        address=f"http://{ec2_instance.aws_public_ip}:8000",
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
            return datasets_on_scheduler is not None
