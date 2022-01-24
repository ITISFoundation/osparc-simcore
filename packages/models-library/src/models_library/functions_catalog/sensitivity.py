from typing import Any, Dict, List

from pydantic import schema_of

from ..services import Author, ServiceDockerData, ServiceType
from ._constants import FRONTEND_SERVICE_KEY_PREFIX

OM = Author(name="Odei Maiz", email="maiz@itis.swiss", affiliation="IT'IS")
# TODO: how to avoid explicit names here to define ownership?
#


def to_schema(type_: Any) -> Dict[str, Any]:
    # FIXME: this is chapuzaaaaa
    # NOTE: schema_of has already a cache in place of 2MB
    schema = schema_of(type_)
    schema.pop("title")
    if set(schema.keys()) == "type":
        return schema["type"]
    return schema


def sensitivity_meta() -> ServiceDockerData:
    return ServiceDockerData(
        key=f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/sensitivity",
        version="1.0.0",
        type=ServiceType.FRONTEND,
        name="Sensitivity iterator",
        description="Increases/decreases one dimension of the reference parameters at every iteration",
        authors=[
            OM,
        ],
        contact=OM.email,
        **_io_signature(),
    )


def _io_signature() -> Dict[str, Any]:
    return {
        "inputs": {
            "in_1": {
                "label": "paramrefs",
                "description": "reference parameters",
                "type": to_schema(List[float]),
            },
            "in_2": {
                "label": "paramdiff",
                "description": "diff parameters",
                "type": to_schema(List[float]),
            },
            "in_3": {
                "label": "diff_or_fact",
                "description": "Applies difference (true) or factor (false)",
                "type": to_schema(bool),
            },
        },
        "outputs": {
            "out_1": {
                "label": "i",
                "description": "dimension index that was modified",
                "type": to_schema(int),
            },
            "out_2": {
                "label": "paramtestplus",
                "description": "increased parameter",
                "type": to_schema(List[float]),
            },
            "out_3": {
                "label": "paramtestminus",
                "description": "decreased parameter",
                "type": to_schema(List[float]),
            },
        },
    }
