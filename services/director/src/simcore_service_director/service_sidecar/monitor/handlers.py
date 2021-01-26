import logging

from .handlers_base import BaseEventHandler
from typing import List

from aiohttp.web import Application

from ..docker_compose_assembly import assemble_spec
from .models import MonitorData, ServiceSidecarStatus
from .service_sidecar_api import get_api_client

logger = logging.getLogger(__name__)


class RunDockerComposeUp(BaseEventHandler):
    """Runs the docker-compose up command when and composes the spec if a service requires it"""

    @classmethod
    async def will_trigger(cls, previous: MonitorData, current: MonitorData) -> bool:
        return (
            current.service_sidecar.overall_status.status == ServiceSidecarStatus.OK
            and current.service_sidecar.is_available == True
            and current.service_sidecar.compose_spec_submitted == False
        )

    @classmethod
    async def action(
        cls, app: Application, previous: MonitorData, current: MonitorData
    ) -> None:
        logger.debug("Getting docker compose spec for service %s", current.service_name)

        api_client = get_api_client(app)
        service_sidecar_endpoint = current.service_sidecar.endpoint

        # TODO: replace service_key and service_tag
        compose_spec = await assemble_spec(service_key="", service_tag="")

        compose_spec_was_applied = await api_client.start_or_update_compose_service(
            service_sidecar_endpoint, compose_spec
        )

        # compose spec was submitted
        current.service_sidecar.compose_spec_submitted = True

        # singal there is a problem with the service-sidecar
        if not compose_spec_was_applied:
            current.service_sidecar.overall_status.update_failing_status(
                "Could not apply docker-compose up. Ask an admin to check director logs for details."
            )


class ServicesInspect(BaseEventHandler):
    """Inspects all spawned containers for the sidecar-service"""

    @classmethod
    async def will_trigger(cls, previous: MonitorData, current: MonitorData) -> bool:
        return (
            current.service_sidecar.overall_status.status == ServiceSidecarStatus.OK
            and current.service_sidecar.is_available == True
            and current.service_sidecar.compose_spec_submitted == True
        )

    @classmethod
    async def action(
        cls, app: Application, previous: MonitorData, current: MonitorData
    ) -> None:
        api_client = get_api_client(app)
        service_sidecar_endpoint = current.service_sidecar.endpoint

        containers_inspect = await api_client.containers_inspect(
            service_sidecar_endpoint
        )
        if containers_inspect is None:
            # this means that the service was degrated and we need to do something?
            current.service_sidecar.overall_status.update_failing_status(
                f"Could not get containers_inspect for {current.service_name}. "
                "Ask and admin to check director logs for details."
            )

        # TODO: parse and store service info here
        logger.info("Container inspect, result %s", containers_inspect)


# register all handlers defined in this module here
# A list is essential to guarantee execution order
REGISTERED_HANDLERS: List[BaseEventHandler] = [
    RunDockerComposeUp,
    ServicesInspect,
]
