from typing import Optional

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import OM, create_fake_thumbnail_url, register
from .constants import FUNCTION_SERVICE_KEY_PREFIX


def create_metadata(type_name: str, prefix: Optional[str] = None) -> ServiceDockerData:
    prefix = prefix or type_name
    LABEL = f"{type_name.capitalize()} probe"

    return ServiceDockerData.parse_obj(
        {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/iterator-consumer/probe/{prefix}",
            "version": "1.0.0",
            "type": ServiceType.FRONTEND,
            "name": LABEL,
            "description": f"Probes its input for {type_name} values",
            "thumbnail": create_fake_thumbnail_url(f"{type_name}"),
            "authors": [
                OM,
            ],
            "contact": OM.email,
            "inputs": {
                "in_1": {
                    "label": f"{type_name} Probe",
                    "description": f"Captures {type_name} values attached to it",
                    "defaultValue": 0,
                    "type": type_name,
                }
            },
            "outputs": {},
        }
    )


META_NUMBER, META_BOOL, META_INT, META_STR = [
    create_metadata(t) for t in ("number", "boolean", "integer", "string")
]

REGISTRY = register(META_NUMBER, META_BOOL, META_INT, META_STR)
