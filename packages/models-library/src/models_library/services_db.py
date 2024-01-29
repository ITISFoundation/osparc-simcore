"""

NOTE: to dump json-schema from CLI use
    python -c "from models_library.services import ServiceDockerData as cls; print(cls.schema_json(indent=2))" > services-schema.json
"""


from pydantic import ConfigDict, Field
from pydantic.types import PositiveInt

from .services import ServiceKeyVersion, ServiceMetaData
from .services_access import ServiceGroupAccessRights

# -------------------------------------------------------------------
# Databases models
#  - table services_meta_data
#  - table services_access_rights


class ServiceMetaDataAtDB(ServiceKeyVersion, ServiceMetaData):
    # for a partial update all members must be Optional
    classifiers: list[str] | None = Field([])
    owner: PositiveInt | None = None
    model_config = ConfigDict(from_attributes=True)


class ServiceAccessRightsAtDB(ServiceKeyVersion, ServiceGroupAccessRights):
    gid: PositiveInt = Field(..., description="defines the group id", examples=[1])
    product_name: str = Field(
        ..., description="defines the product name", examples=["osparc"]
    )
    model_config = ConfigDict(from_attributes=True)
