from typing import Final

from ...services import (
    LATEST_INTEGRATION_VERSION,
    ServiceMetaDataPublished,
    ServiceType,
)
from .._key_labels import FUNCTION_SERVICE_KEY_PREFIX
from .._utils import OM, FunctionServices

META: Final = ServiceMetaDataPublished.model_validate(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/file-picker",
        "version": "1.0.0",
        "type": ServiceType.FRONTEND,
        "name": "File Picker",
        "description": "File Picker",
        "authors": [
            OM,
        ],
        "contact": OM.email,
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


services = FunctionServices()
services.add(
    meta=META,
)
