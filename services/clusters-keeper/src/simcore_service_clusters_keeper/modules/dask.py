import contextlib
import logging

import dask_gateway
from aiohttp.client_exceptions import ClientError

from ..models import EC2InstanceData

_logger = logging.getLogger(__name__)


async def ping_gateway(ec2_instance: EC2InstanceData) -> bool:
    basic_auth = dask_gateway.BasicAuth(username="bing", password="asdf")
    with contextlib.suppress(ClientError):
        async with dask_gateway.Gateway(
            address=f"http://{ec2_instance.aws_public_ip}:8000",
            auth=basic_auth,
            asynchronous=True,
        ) as gateway:
            cluster_reports = await gateway.list_clusters()
        _logger.info("found %s clusters", len(cluster_reports))
        return True

    return False
