from models_library.services import ServiceKey, ServiceVersion
from models_library.users import GroupID

from ..schemas.services_specifications import ServiceSpecifications


class ServiceSpecificationsAtDB(ServiceSpecifications):
    service_key: ServiceKey
    service_version: ServiceVersion
    gid: GroupID

    class Config(ServiceSpecifications.Config):
        orm_mode: bool = True
