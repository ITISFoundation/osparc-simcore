from typing import Optional

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import OM, create_fake_thumbnail_url, register
from .constants import FUNCTION_SERVICE_KEY_PREFIX


def create_metadata(type_name: str, prefix: Optional[str] = None) -> ServiceDockerData:
    prefix = prefix or type_name
    LABEL = f"{type_name.capitalize()} iterator"
    return ServiceDockerData.parse_obj(
        {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/{prefix}-range",
            "version": "1.0.0",
            "type": ServiceType.BACKEND,
            "name": LABEL,
            "description": "Iterates over a sequence of integers from start (inclusive) to stop (exclusive) by step",
            "thumbnail": create_fake_thumbnail_url(f"{type_name}"),
            "authors": [
                OM,
            ],
            "contact": OM.email,
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
                    "defaultValue": 2,
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
                    "label": f"An {type_name}",
                    "description": f"One {type_name} per iteration",
                    "type": type_name,
                }
            },
        }
    )


META_INT = create_metadata("integer", prefix="int")

REGISTRY = register(META_INT)
