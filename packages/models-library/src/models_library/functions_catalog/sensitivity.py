from typing import Any, Dict, List

from pydantic import schema_json_of

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._constants import EN, FRONTEND_SERVICE_KEY_PREFIX, OM

# TODO: how to avoid explicit names here to define ownership?
#


LIST_NUMBERS_SCHEMA: str = schema_json_of(List[float], title="list[number]")


def create_metadata() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/sensitivity",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Sensitivity iterator",
        description="Increases/decreases one dimension of the reference parameters at every iteration",
        authors=[EN, OM],
        contact=OM["email"],
        **_io_signature(),
    )


def _io_signature() -> Dict[str, Any]:
    return {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "inputs": {
            "in_1": {
                "label": "paramrefs",
                "description": "reference parameters",
                "type": "as_schema",
                "content_schema": LIST_NUMBERS_SCHEMA,
            },
            "in_2": {
                "label": "paramdiff",
                "description": "diff parameters",
                "type": "as_schema",
                "content_schema": LIST_NUMBERS_SCHEMA,
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
                "type": "as_schema",
                "content_schema": LIST_NUMBERS_SCHEMA,
            },
            "out_3": {
                "label": "paramtestminus",
                "description": "decreased parameters",
                "type": "as_schema",
                "content_schema": LIST_NUMBERS_SCHEMA,
            },
        },
    }
