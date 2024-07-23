from datetime import datetime
from typing import Any, ClassVar

from models_library.products import ProductName
from models_library.services_access import ServiceGroupAccessRights
from models_library.services_base import ServiceKeyVersion
from models_library.services_metadata_editable import ServiceMetaDataEditable
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import BaseModel, Field
from pydantic.types import PositiveInt
from simcore_postgres_database.models.services_compatibility import CompatiblePolicyDict


class ServiceMetaDataAtDB(ServiceKeyVersion, ServiceMetaDataEditable):
    # for a partial update all members must be Optional
    classifiers: list[str] | None = Field(default_factory=list)
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
                "version_display": "S4L X",
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


class ReleaseFromDB(BaseModel):
    version: ServiceVersion
    deprecated: datetime | None
    created: datetime
    compatibility_policy: CompatiblePolicyDict | None


class ServiceWithHistoryFromDB(BaseModel):
    key: ServiceKey
    version: ServiceVersion
    # display
    name: str
    description: str
    thumbnail: str | None
    version_display: str | None
    # ownership
    owner_email: str | None
    # tags
    classifiers: list[str]
    quality: dict[str, Any]
    # lifetime
    created: datetime
    modified: datetime
    deprecated: datetime | None
    # releases
    history: list[ReleaseFromDB]


assert (  # nosec
    set(ReleaseFromDB.__fields__)
    .difference({"compatibility_policy"})
    .issubset(set(ServiceWithHistoryFromDB.__fields__))
)


class ServiceAccessRightsAtDB(ServiceKeyVersion, ServiceGroupAccessRights):
    gid: PositiveInt
    product_name: ProductName

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
