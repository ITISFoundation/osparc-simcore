from typing import Optional

from models_library.services import (
    ServiceAccessRights,
    ServiceDockerData,
    ServiceMetaData,
)
from pydantic import EmailStr


# OpenAPI models (contain both service metadata and access rights)
class ServiceUpdate(ServiceMetaData, ServiceAccessRights):
    pass


class ServiceOut(
    ServiceDockerData, ServiceAccessRights, ServiceMetaData
):  # pylint: disable=too-many-ancestors
    owner: Optional[EmailStr]
