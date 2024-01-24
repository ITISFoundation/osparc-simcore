from typing import Any

from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import (
    NodeGet,
    NodeGetIdle,
    NodeGetUnknown,
)


def get_service_status_serialization_options(
    service_status: NodeGetIdle | NodeGetUnknown | DynamicServiceGet | NodeGet,
) -> dict[str, Any]:

    by_alias: bool = isinstance(service_status, DynamicServiceGet)
    return {"by_alias": by_alias}
