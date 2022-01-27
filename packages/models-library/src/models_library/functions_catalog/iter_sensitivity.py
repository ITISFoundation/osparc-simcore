from typing import Any, Dict, List

from pydantic import schema_of

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import EN, FRONTEND_SERVICE_KEY_PREFIX, OM, get_fake_thumbnail, register

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
        "thumbnail": get_fake_thumbnail("sensitivity"),
        "inputs": {
            "paramrefs": {
                "label": "paramrefs",
                "description": "reference parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
            "paramdiff": {
                "label": "paramdiff",
                "description": "diff parameters",
                "type": "ref_contentSchema",
                "contentSchema": LIST_NUMBERS_SCHEMA,
            },
            "diff_or_fact": {
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
