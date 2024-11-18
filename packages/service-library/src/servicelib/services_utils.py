import urllib.parse

from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import (
    NodeGet,
    NodeGetIdle,
    NodeGetUnknown,
)
from models_library.services import ServiceType


def get_service_from_key(service_key: str) -> ServiceType:
    decoded_service_key = urllib.parse.unquote_plus(service_key)
    encoded_service_type = decoded_service_key.split("/")[2]
    if encoded_service_type == "comp":
        encoded_service_type = "computational"
    return ServiceType(encoded_service_type)


def get_status_as_dict(
    status: NodeGetIdle | NodeGetUnknown | DynamicServiceGet | NodeGet,
) -> dict:
    """shared between different backend services to guarantee same result to frontend"""
    return (
        status.model_dump(by_alias=True)
        if isinstance(status, DynamicServiceGet)
        else status.model_dump()
    )
