from typing import Optional

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import FRONTEND_SERVICE_KEY_PREFIX, OM, register


def create_metadata(type_name: str, prefix: Optional[str] = None) -> ServiceDockerData:
    prefix = prefix or type_name

    return ServiceDockerData.parse_obj(
        {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/{prefix}-range",
            "version": "1.0.0",
            "type": ServiceType.FRONTEND,
            "name": f"{type_name.capitalize()} iterator",
            "description": f"{type_name.capitalize()} iterator. range()",
            "authors": [
                OM,
            ],
            "contact": OM["email"],
            "inputs": {
                "linspace_start": {
                    "label": "Start",
                    "description": "Linear space Start",
                    "defaultValue": 0,
                    "type": type_name,
                },
                "linspace_stop": {
                    "label": "Stop",
                    "description": "Linear space Stop",
                    "defaultValue": 1,
                    "type": type_name,
                },
                "linspace_step": {
                    "label": "Step",
                    "description": "Linear space Step",
                    "defaultValue": 1,
                    "type": type_name,
                },
            },
            "outputs": {
                "out_1": {
                    "label": "An {type_name}}",
                    "description": "One {type_name} per iteration",
                    "type": type_name,
                }
            },
        }
    )


META_INT = create_metadata("integer", prefix="int")
META_NUM = create_metadata("number")

# TODO: PC-> OM register more or even one generic?
REGISTRY = register(META_INT)
