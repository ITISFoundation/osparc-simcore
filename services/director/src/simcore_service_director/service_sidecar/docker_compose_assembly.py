from copy import deepcopy
from typing import Dict, Any

import yaml
from aiohttp.web import Application


from .config import get_settings, ServiceSidecarSettings

CONTAINER_NAME = "container"
BASE_SERVICE_SPEC: Dict[str, Any] = {
    "version": "3.7",
    "services": {CONTAINER_NAME: {}},
}


async def assemble_spec(app: Application, service_key: str, service_tag: str) -> str:
    """returns a docker-compose spec which will be use by the service-sidecar to start the service """
    settings: ServiceSidecarSettings = get_settings(app)

    service_spec = deepcopy(BASE_SERVICE_SPEC)
    service_spec["services"][CONTAINER_NAME] = {
        "image": f"{settings.resolved_registry_url}/{service_key}:{service_tag}"
    }

    return yaml.safe_dump(service_spec)
