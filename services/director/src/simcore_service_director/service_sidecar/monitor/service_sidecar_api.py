import logging

from typing import Optional, Dict, Any
from aiohttp.web import Application
from .models import MonitorData
import httpx

logger = logging.getLogger(__name__)


KEY_SERVICE_SIDECAR_API_CLIENT = f"{__name__}.ServiceSidecarClient"

# pylint: disable=useless-return
def log_error_and_return(
    response: httpx.Response,
    e: Optional[Exception] = None,
    retrun_value: Optional[Any] = None,
) -> None:
    """Logs error and returns return_value"""
    if e is None:
        logging.warning(
            "error during request status=%s, body=%s",
            response.status_code,
            response.text,
        )
    else:
        logging.warning(
            "error during request status=%s, body=%s\n\n%s\nThe above error occurred",
            response.status_code,
            response.text,
            str(e),
        )
    return retrun_value


def get_url(service_sidecar_endpoint: str, postfix: str) -> str:
    """formats and returns an url for the request"""
    url = f"{service_sidecar_endpoint}{postfix}"
    logging.debug("httpx requests url %s", url)
    return url


class ServiceSidecarClient:
    """Will handle connections to the service sidecar"""

    def __init__(self):
        timeout = httpx.Timeout(1.0, connect=1.0)
        self.httpx_client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self.httpx_client.aclose()

    async def is_healthy(self, service_sidecar_endpoint: str) -> bool:
        """retruns True if service is UP and running else False"""
        url = get_url(service_sidecar_endpoint, "/health")
        logging.debug("Requesting url %s", url)
        try:
            response = await self.httpx_client.get(url=url)
            if response.status_code != 200:
                return False

            return response.json()["is_healthy"]
        except httpx.HTTPError:
            return False
        return True

    async def containers_inspect(
        self, service_sidecar_endpoint: str
    ) -> Optional[Dict[str, Any]]:
        """returns: None in case of error, otherwise a dict will be returned"""
        url = get_url(service_sidecar_endpoint, "/containers/inspect")
        try:
            response = await self.httpx_client.get(url=url)
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return None

            return response.json()
        except httpx.HTTPError as e:
            logging.warning(
                "While requesting %s the following error occurred: %s", url, str(e)
            )
            return None

    async def start_or_update_compose_service(
        self, service_sidecar_endpoint: str, compose_spec: str
    ) -> bool:
        """returns: True if the compose spec was applied """
        url = get_url(service_sidecar_endpoint, "/compose")
        try:
            response = await self.httpx_client.post(url, data=compose_spec)
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return False

            # request was ok
            logger.info("Applied spec result %s", response.text)
            return True
        except httpx.HTTPError as e:
            logging.warning(
                "While requesting %s the following error occurred: %s", url, str(e)
            )
            return False


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
    service_endpoint = input_monitor_data.service_sidecar.endpoint

    # update service health
    is_healthy = await api_client.is_healthy(service_endpoint)
    output_monitor_data.service_sidecar.is_available = is_healthy

    return output_monitor_data