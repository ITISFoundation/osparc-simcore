from typing import Optional

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import FRONTEND_SERVICE_KEY_PREFIX, OM, get_fake_thumbnail, register


def create_metadata(type_name: str, prefix: Optional[str] = None) -> ServiceDockerData:
    prefix = prefix or type_name

    return ServiceDockerData.parse_obj(
        {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": f"{FRONTEND_SERVICE_KEY_PREFIX}/iterator-consumer/probe/{prefix}",
            "version": "1.0.0",
            "type": ServiceType.FRONTEND,
            "name": "Probe Sensor - Integer",
            "description": "Integer iterator consumer.",
            "thumbnail": get_fake_thumbnail(f"{type_name}"),
            "authors": [
                OM,
            ],
            "contact": OM["email"],
            "inputs": {
                "in_1": {
                    "label": "Iterator consumer",
                    "description": "Iterator consumer",
                    "defaultValue": 0,
                    "type": "integer",
                }
            },
            "outputs": {},
        }
    )


META_NUMBER, META_BOOL, META_INT, META_STR = [
    create_metadata(t) for t in ("number", "boolean", "integer", "string")
]

# TODO: PC-> OM register more or even one generic?
REGISTRY = register(META_INT)
