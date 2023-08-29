import asyncio
import logging

import dask_gateway
from aiohttp.client_exceptions import ClientError
from pydantic import SecretStr

from ..models import EC2InstanceData

_logger = logging.getLogger(__name__)


async def ping_gateway(
    ec2_instance: EC2InstanceData, gateway_password: SecretStr
) -> bool:
    basic_auth = dask_gateway.BasicAuth(
        username="clusters-keeper", password="my_secure_P1ssword"
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
