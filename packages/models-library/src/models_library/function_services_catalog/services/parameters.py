from ...services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from .._key_labels import FUNCTION_SERVICE_KEY_PREFIX
from .._utils import OM, FunctionServices, create_fake_thumbnail_url


def create_metadata(
    output_type: str, output_name: str | None = None
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


META_NUMBER, META_BOOL, META_INT, META_STR = (
    create_metadata(output_type=t) for t in ("number", "boolean", "integer", "string")
)

META_ARRAY = ServiceDockerData.parse_obj(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/parameter/array",
        "version": "1.0.0",
        "type": ServiceType.FRONTEND,
        "name": "Array Parameter",
        "description": "Parameter of type array",
        "thumbnail": create_fake_thumbnail_url("array"),
        "authors": [
            OM,
        ],
        "contact": OM.email,
        "inputs": {},
        "outputs": {
            "out_1": {
                "label": "list[number]",
                "description": "array",
                "type": "ref_contentSchema",
                "contentSchema": {
                    "title": "list[number]",
                    "type": "array",
                    "items": {"type": "number"},
                },
            }
        },
    }
)


services = FunctionServices()
for m in (META_NUMBER, META_BOOL, META_INT, META_STR, META_ARRAY):
    services.add(meta=m)
