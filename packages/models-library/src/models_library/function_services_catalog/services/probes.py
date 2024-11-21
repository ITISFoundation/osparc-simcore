from typing import Final

from ...services import ServiceMetaDataPublished, ServiceType
from ...services_constants import LATEST_INTEGRATION_VERSION
from .._key_labels import FUNCTION_SERVICE_KEY_PREFIX
from .._utils import OM, WVG, FunctionServices, create_fake_thumbnail_url


def _create_metadata(type_name: str) -> ServiceMetaDataPublished:
    obj: ServiceMetaDataPublished = ServiceMetaDataPublished.model_validate(
        {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/iterator-consumer/probe/{type_name}",
            "version": "1.0.0",
            "type": ServiceType.FRONTEND,
            "name": f"{type_name.capitalize()} probe",
            "description": f"Captures {type_name} values at its inputs",
            "thumbnail": create_fake_thumbnail_url(f"{type_name}"),
            "authors": [
                OM,
            ],
            "contact": OM.email,
            "inputs": {
                "in_1": {
                    "label": f"{type_name}_probe",
                    "description": f"Output {type_name} value",
                    # NOTE: no default provided to input probes
                    "type": type_name,
                }
            },
            "outputs": {},
        }
    )
    return obj


META_NUMBER: Final = _create_metadata("number")
META_BOOL: Final = _create_metadata("boolean")
META_INT: Final = _create_metadata("integer")
META_STR: Final = _create_metadata("string")
META_ARRAY: Final = ServiceMetaDataPublished.model_validate(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/iterator-consumer/probe/array",
        "version": "1.0.0",
        "type": ServiceType.FRONTEND,
        "name": "Array probe",
        "description": "Probes its input for array values",
        "thumbnail": create_fake_thumbnail_url("array"),
        "authors": [
            OM,
        ],
        "contact": OM.email,
        "inputs": {
            "in_1": {
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
        "outputs": {},
    }
)

META_FILE: Final = ServiceMetaDataPublished.model_validate(
    {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/iterator-consumer/probe/file",
        "version": "1.0.0",
        "type": ServiceType.FRONTEND,
        "name": "File probe",
        "description": "Probes its input for files",
        "thumbnail": create_fake_thumbnail_url("file"),
        "authors": [
            WVG,
        ],
        "contact": WVG.email,
        "inputs": {
            "in_1": {
                "label": "file",
                "description": "file",
                "type": "data:*/*",
            }
        },
        "outputs": {},
    }
)


def is_probe_service(service_key: str) -> bool:
    return service_key.startswith(
        f"{FUNCTION_SERVICE_KEY_PREFIX}/iterator-consumer/probe/"
    )


services = FunctionServices()
for m in (META_NUMBER, META_BOOL, META_INT, META_STR, META_ARRAY, META_FILE):
    assert is_probe_service(m.key)  # nosec
    services.add(meta=m)
