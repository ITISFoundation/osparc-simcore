import logging

from aiohttp.web import Application
from .models import MonitorData


logger = logging.getLogger(__name__)

# store the client in the app

KEY_SERVICE_SIDECAR_API_CLIENT = f"{__name__}.ServiceSidecarClient"


class ServiceSidecarClient:
    pass


def setup_api_client(app: Application) -> None:
    app[KEY_SERVICE_SIDECAR_API_CLIENT] = ServiceSidecarClient()


def get_api_client(app: Application) -> ServiceSidecarClient:
    return app[KEY_SERVICE_SIDECAR_API_CLIENT]


async def query_service(
    app: Application, input_monitor_data: MonitorData
) -> MonitorData:
    # TODO: call into service-sidecar API for to update the data
    logger.debug("No transformation applied to %s", input_monitor_data)

    api_client = get_api_client(app)

    return input_monitor_data