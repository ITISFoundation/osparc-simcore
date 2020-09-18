from typing import Optional

from pydantic import EmailStr

from models_library.services import (
    ServiceAccessRights,
    ServiceDockerData,
    ServiceMetaData,
)


# OpenAPI models (contain both service metadata and access rights)
class ServiceUpdate(ServiceMetaData, ServiceAccessRights):
    pass


class ServiceOut(
    ServiceDockerData, ServiceAccessRights, ServiceMetaData
):  # pylint: disable=too-many-ancestors
    owner: Optional[EmailStr]
