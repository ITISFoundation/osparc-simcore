from typing import Final

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import FRONTEND_SERVICE_KEY_PREFIX, OM, register

META: Final = ServiceDockerData.parse_obj(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FRONTEND_SERVICE_KEY_PREFIX}/file-picker",
        "version": "1.0.0",
        "type": ServiceType.FRONTEND,
        "name": "File Picker",
        "description": "File Picker",
        "authors": [
            OM,
        ],
        "contact": OM["email"],
        "inputs": {},
        "outputs": {
            "outFile": {
                "displayOrder": 0,
                "label": "File",
                "description": "Chosen File",
                "type": "data:*/*",
            }
        },
    }
)


REGISTRY = register(META)
