from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import BaseModel, HttpUrl


class ServiceMetadata(BaseModel):
    key: ServiceKey
    version: ServiceVersion
    thumbnail: HttpUrl | None
