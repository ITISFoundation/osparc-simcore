from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.groups import GroupID
from models_library.services import ServiceKey, ServiceVersion
from pydantic import ConfigDict


class ServiceSpecificationsAtDB(ServiceSpecifications):
    service_key: ServiceKey
    service_version: ServiceVersion
    gid: GroupID

    model_config = ConfigDict(from_attributes=True)
