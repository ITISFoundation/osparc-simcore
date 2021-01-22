import logging

from aiohttp.web import Application
from .models import MonitorData
import httpx

logger = logging.getLogger(__name__)


KEY_SERVICE_SIDECAR_API_CLIENT = f"{__name__}.ServiceSidecarClient"


class ServiceSidecarClient:
    """Will handle connections to the service sidecar"""

    def __init__(self):
        timeout = httpx.Timeout(1.0, connect=1.0)
        self.httpx_client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self.httpx_client.aclose()

    async def is_healthy(self, service_sidecar_endpoint: str) -> bool:
        """retruns True if service is UP and running else False"""
        url = f"{service_sidecar_endpoint}/health"
        logging.debug("Requesting url %s", url)
        try:
            response = await self.httpx_client.get(url=url)
            if response.status_code != 200:
                return False

            return response.json()["is_healthy"]
        except httpx.HTTPError:
            return False
        return True


async def setup_api_client(app: Application) -> None:
    logger.debug("service-sidecar api client setup")
    app[KEY_SERVICE_SIDECAR_API_CLIENT] = ServiceSidecarClient()


async def shutdown_api_client(app: Application) -> None:
    logger.debug("service-sidecar api client shutdown")
    service_sidecar_client = app[KEY_SERVICE_SIDECAR_API_CLIENT]
    await service_sidecar_client.close()


def get_api_client(app: Application) -> ServiceSidecarClient:
    return app[KEY_SERVICE_SIDECAR_API_CLIENT]


async def query_service(
    app: Application, input_monitor_data: MonitorData
) -> MonitorData:
    # make a copy of the original
    output_monitor_data = input_monitor_data.copy(deep=True)

    api_client = get_api_client(app)

    is_healthy = await api_client.is_healthy(
        input_monitor_data.service_sidecar.endpoint
    )
    # TODO: check if below logic is fine
    # if health is ok, other handlers can trigger and more actions can be ran
    # this needs to be setup further?

    # determine if service is available
    output_monitor_data.service_sidecar.is_available = is_healthy

    return output_monitor_data