from typing import Any, Dict, List

from pydantic import schema_of

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import EN, FRONTEND_SERVICE_KEY_PREFIX, OM, register

# TODO: how to avoid explicit names here to define ownership?
#


LIST_NUMBERS_SCHEMA: Dict[str, Any] = schema_of(List[float], title="list[number]")


META = ServiceDockerData.parse_obj(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/sensitivity",
        "version": "1.0.0",
        "type": ServiceType.FRONTEND,
        "name": "Sensitivity iterator",
        "description": "Increases/decreases one dimension of the reference parameters at every iteration",
        "authors": [EN, OM],
        "contact": OM["email"],
        "inputs": {
            "in_1": {
                "label": "paramrefs",
                "description": "reference parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
            "in_2": {
                "label": "paramdiff",
                "description": "diff parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
            "in_3": {
                "label": "diff_or_fact",
                "description": "Applies difference (true) or factor (false)",
                "type": "boolean",
            },
        },
        "outputs": {
            "out_1": {
                "label": "i",
                "description": "dimension index that was modified",
                "type": "integer",
            },
            "out_2": {
                "label": "paramtestplus",
                "description": "increased parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
            "out_3": {
                "label": "paramtestminus",
                "description": "decreased parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
        },
    }
)

REGISTRY = register(META)
