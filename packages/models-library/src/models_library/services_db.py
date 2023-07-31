"""

NOTE: to dump json-schema from CLI use
    python -c "from models_library.services import ServiceDockerData as cls; print(cls.schema_json(indent=2))" > services-schema.json
"""

from typing import Any, ClassVar

from pydantic import Field
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
    owner: PositiveInt | None

    class Config:
        orm_mode = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "version": "1.0.9",
                "owner": 8,
                "name": "sim4life",
                "description": "s4l web",
                "thumbnail": "http://thumbnailit.org/image",
                "created": "2021-01-18 12:46:57.7315",
                "modified": "2021-01-19 12:45:00",
                "deprecated": "2099-01-19 12:45:00",
                "quality": {
                    "enabled": True,
                    "tsr_target": {
                        f"r{n:02d}": {"level": 4, "references": ""}
                        for n in range(1, 11)
                    },
                    "annotations": {
                        "vandv": "",
                        "limitations": "",
                        "certificationLink": "",
                        "certificationStatus": "Uncertified",
                    },
                    "tsr_current": {
                        f"r{n:02d}": {"level": 0, "references": ""}
                        for n in range(1, 11)
                    },
                },
            }
        }


class ServiceAccessRightsAtDB(ServiceKeyVersion, ServiceGroupAccessRights):
    gid: PositiveInt = Field(..., description="defines the group id", example=1)
    product_name: str = Field(
        ..., description="defines the product name", example="osparc"
    )

    class Config:
        orm_mode = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "version": "1.0.9",
                "gid": 8,
                "execute_access": True,
                "write_access": True,
                "product_name": "osparc",
                "created": "2021-01-18 12:46:57.7315",
                "modified": "2021-01-19 12:45:00",
            }
        }
