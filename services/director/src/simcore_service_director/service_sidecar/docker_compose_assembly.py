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
    # registry.osparc-master.speag.com/simcore/services/dynamic/jupyter-octave-python-math:1.5.2
    image = f"{service_key}:{service_tag}"
    service_spec["services"] = {
        "whocontainer": {
            "image": image,
        }
    }

    return yaml.safe_dump(service_spec)
