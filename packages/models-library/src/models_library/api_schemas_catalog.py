from pydantic import BaseModel

from .services import ServiceKey, ServiceVersion


class AccessRightsRules(BaseModel):
    execute_access: bool
    write_access: bool


class ServiceAccessRightsGet(BaseModel):
    service_key: ServiceKey
    service_version: ServiceVersion
    gids_with_access_rights: dict[int, dict[str, bool]]
