from typing import Optional

from ..services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from ._utils import OM, create_fake_thumbnail_url, register
from .constants import FUNCTION_SERVICE_KEY_PREFIX


def create_metadata(
    output_type: str, output_name: Optional[str] = None
) -> ServiceDockerData:
    """
    Represents a parameter (e.g. "x":5) in a study

    This is a parametrized node (or param-node in short)
    """
    LABEL = output_name or f"{output_type.capitalize()} Parameter"
    DESCRIPTION = f"Parameter of type {output_type}"
    output_name = output_name or "out_1"

    meta = ServiceDockerData.parse_obj(
        {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/parameter/{output_type}",
            "version": "1.0.0",
            "type": ServiceType.FRONTEND,
            "name": LABEL,
            "description": DESCRIPTION,
            "thumbnail": create_fake_thumbnail_url(f"{output_type}"),
            "authors": [
                OM,
            ],
            "contact": OM.email,
            "inputs": {},
            "outputs": {
                "out_1": {
                    "label": output_name,
                    "description": DESCRIPTION,
                    "type": output_type,
                }
            },
        }
    )

    assert meta.outputs is not None  # nosec
    assert list(meta.outputs.keys()) == ["out_1"], "name used in front-end"  # nosec
    return meta


META_NUMBER, META_BOOL, META_INT, META_STR = [
    create_metadata(output_type=t) for t in ("number", "boolean", "integer", "string")
]

# TODO: PC-> OM register more generic?
REGISTRY = register(META_NUMBER, META_BOOL, META_INT, META_STR)
