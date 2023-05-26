from pydantic import BaseModel

from .services import ServiceKey, ServiceVersion


class ServiceAccessRightsGet(BaseModel):
    service_key: ServiceKey
    service_version: ServiceVersion
    gids_with_access_rights: dict[int, dict[str, bool]]
