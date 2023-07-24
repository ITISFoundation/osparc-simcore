from ...services import ServiceKey, ServiceVersion
from ...users import GroupID
from ..schemas.services_specifications import ServiceSpecifications


class ServiceSpecificationsAtDB(ServiceSpecifications):
    service_key: ServiceKey
    service_version: ServiceVersion
    gid: GroupID

    class Config(ServiceSpecifications.Config):
        orm_mode: bool = True
