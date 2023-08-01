from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import GroupID


class ServiceSpecificationsAtDB(ServiceSpecifications):
    service_key: ServiceKey
    service_version: ServiceVersion
    gid: GroupID

    class Config(ServiceSpecifications.Config):
        orm_mode: bool = True
