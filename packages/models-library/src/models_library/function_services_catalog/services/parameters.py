from typing import Final

from ...services import ServiceMetaDataPublished, ServiceType
from ...services_constants import LATEST_INTEGRATION_VERSION
from .._key_labels import FUNCTION_SERVICE_KEY_PREFIX
from .._utils import OM, FunctionServices, create_fake_thumbnail_url


def _create_metadata(type_name: str) -> ServiceMetaDataPublished:
    """
    Represents a parameter (e.g. "x":5) in a study

    This is a parametrized node (or param-node in short)
    """
    meta = ServiceMetaDataPublished.model_validate(
        {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/parameter/{type_name}",
            "version": "1.0.0",
            "type": ServiceType.FRONTEND,
            "name": f"{type_name.capitalize()} parameter",
            "description": f"Produces a {type_name} value at its outputs",
            "thumbnail": create_fake_thumbnail_url(f"{type_name}"),
            "authors": [
                OM,
            ],
            "contact": OM.email,
            "inputs": {},
            "outputs": {
                "out_1": {
                    "label": f"{type_name}_source",
                    "description": f"Input {type_name} value",
                    "type": type_name,
                }
            },
        }
    )

    assert meta.outputs is not None  # nosec
    assert list(meta.outputs.keys()) == ["out_1"], "name used in front-end"  # nosec
    return meta


META_NUMBER: Final = _create_metadata(type_name="number")
META_BOOL: Final = _create_metadata(type_name="boolean")
META_INT: Final = _create_metadata(type_name="integer")
META_STR: Final = _create_metadata(type_name="string")
META_ARRAY: Final = ServiceMetaDataPublished.model_validate(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/parameter/array",
        "version": "1.0.0",
        "type": ServiceType.FRONTEND,
        "name": "Array Parameter",
        "description": "Array of numbers",
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


def is_parameter_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/parameter/")


services = FunctionServices()
for m in (META_NUMBER, META_BOOL, META_INT, META_STR, META_ARRAY):
    assert is_parameter_service(m.key)  # nosec
    services.add(meta=m)
