from ...services import LATEST_INTEGRATION_VERSION, ServiceDockerData, ServiceType
from .._key_labels import FUNCTION_SERVICE_KEY_PREFIX
from .._utils import OM, FunctionServices, create_fake_thumbnail_url


def create_metadata(type_name: str, prefix: str | None = None) -> ServiceDockerData:
    prefix = prefix or type_name
    LABEL = f"{type_name.capitalize()} probe"

    return ServiceDockerData.parse_obj(
        {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": f"{FUNCTION_SERVICE_KEY_PREFIX}/iterator-consumer/probe/{prefix}",
            "version": "1.0.0",
            "type": ServiceType.FRONTEND,
            "name": LABEL,
            "description": f"Probes its input for {type_name} values",
            "thumbnail": create_fake_thumbnail_url(f"{type_name}"),
            "authors": [
                OM,
            ],
            "contact": OM.email,
            "inputs": {
                "in_1": {
                    "label": f"{type_name} Probe",
                    "description": f"Captures {type_name} values attached to it",
                    "defaultValue": 0,
                    "type": type_name,
                }
            },
            "outputs": {},
        }
    )


META_NUMBER, META_BOOL, META_INT, META_STR = (
    create_metadata(t) for t in ("number", "boolean", "integer", "string")
)

META_ARRAY = ServiceDockerData.parse_obj(
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


services = FunctionServices()
for m in (META_NUMBER, META_BOOL, META_INT, META_STR, META_ARRAY):
    services.add(meta=m)
