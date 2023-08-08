from pydantic import BaseModel

from ..services import ServiceKey, ServiceVersion
from ..users import GroupID


class ServiceAccessRightsGet(BaseModel):
    service_key: ServiceKey
    service_version: ServiceVersion
    gids_with_access_rights: dict[GroupID, dict[str, bool]]
