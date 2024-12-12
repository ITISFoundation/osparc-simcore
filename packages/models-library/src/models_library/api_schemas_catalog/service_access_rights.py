from pydantic import BaseModel

from ..groups import GroupID
from ..services import ServiceKey, ServiceVersion


class ServiceAccessRightsGet(BaseModel):
    service_key: ServiceKey
    service_version: ServiceVersion
    gids_with_access_rights: dict[GroupID, dict[str, bool]]
