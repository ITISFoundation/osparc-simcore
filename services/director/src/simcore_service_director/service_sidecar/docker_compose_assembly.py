from copy import deepcopy
from typing import Dict, Any

import yaml


BASE_SERVICE_SPEC: Dict[str, Any] = {
    "version": "3.7",
    "services": {},
}


async def assemble_spec(service_key: str, service_tag: str) -> str:
    """returns a docker-compose spec which will be use by the service-sidecar to start the service """
    service_spec = deepcopy(BASE_SERVICE_SPEC)
    service_spec["services"] = {
        "whocontainer": {
            "container_name": "ohhhhhhh",
            "image": f"{service_key}:{service_tag}",
        }
    }

    return yaml.safe_dump(service_spec)
