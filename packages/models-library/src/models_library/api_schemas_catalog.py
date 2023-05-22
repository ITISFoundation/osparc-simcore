from models_library.users import UserID
from pydantic import BaseModel

from .services import ServiceKey, ServiceVersion


class UserInaccessibleService(BaseModel):
    user_id: UserID
    service_key: ServiceKey
    service_version: ServiceVersion
