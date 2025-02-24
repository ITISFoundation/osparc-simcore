from datetime import datetime
from typing import Annotated, Any

from common_library.basic_types import DEFAULT_FACTORY
from models_library.basic_types import IdInt
from models_library.products import ProductName
from models_library.services_access import ServiceGroupAccessRights
from models_library.services_base import ServiceKeyVersion
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.utils.common_validators import empty_str_to_none_pre_validator
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.config import JsonDict
from pydantic.types import PositiveInt
from simcore_postgres_database.models.services_compatibility import CompatiblePolicyDict


class ServiceMetaDataDBGet(BaseModel):
    # primary-keys
    key: ServiceKey
    version: ServiceVersion

    # ownership
    owner: IdInt | None

    # display
    name: str
    description: str
    description_ui: bool
    thumbnail: Annotated[
        str | None,
        # NOTE: Prevents validation errors caused by empty strings mistakenly
        # set instead of null in the database.
        BeforeValidator(empty_str_to_none_pre_validator),
    ]
    icon: Annotated[
        str | None,
        # NOTE: Prevents validation errors caused by empty strings mistakenly
        # set instead of null in the database.
        BeforeValidator(empty_str_to_none_pre_validator),
    ]
    version_display: Annotated[
        str | None,
        # NOTE: Prevents validation errors caused by empty strings mistakenly
        # set instead of null in the database.
        BeforeValidator(empty_str_to_none_pre_validator),
    ]

    # tagging
    classifiers: list[str]
    quality: dict[str, Any]

    # lifecycle
    created: datetime
    modified: datetime
    deprecated: datetime | None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "example": {
                    "key": "simcore/services/dynamic/reading",
                    "version": "1.0.9",
                    "owner": 8,
                    "name": "reading",
                    "description": "example for service metadata db GET",
                    "description_ui": False,
                    "thumbnail": None,
                    "icon": "https://picsum.photos/50",
                    "version_display": "S4L X",
                    "classifiers": ["foo", "bar"],
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
                    "created": "2021-01-18 12:46:57.7315",
                    "modified": "2021-01-19 12:45:00",
                    "deprecated": "2099-01-19 12:45:00",
                }
            }
        )

    model_config = ConfigDict(
        from_attributes=True, json_schema_extra=_update_json_schema_extra
    )


class ServiceMetaDataDBCreate(BaseModel):
    # primary-keys
    key: ServiceKey
    version: ServiceVersion

    # ownership
    owner: IdInt | None = None

    # display
    name: str
    description: str
    description_ui: bool = False
    thumbnail: str | None = None
    icon: str | None = None
    version_display: str | None = None

    # tagging
    classifiers: Annotated[list[str], Field(default_factory=list)] = DEFAULT_FACTORY
    quality: Annotated[dict[str, Any], Field(default_factory=dict)] = DEFAULT_FACTORY

    # lifecycle
    deprecated: datetime | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    # minimal w/ required values
                    {
                        "key": "simcore/services/dynamic/creating",
                        "version": "1.0.9",
                        "name": "creating",
                        "description": "example for service metadata db CREATE",
                    }
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


class ServiceMetaDataDBPatch(BaseModel):
    # ownership
    owner: IdInt | None = None

    # display
    name: str | None = None
    description: str | None = None
    description_ui: bool = False
    version_display: str | None = None
    thumbnail: str | None = None
    icon: str | None = None

    # tagging
    classifiers: Annotated[list[str], Field(default_factory=list)] = DEFAULT_FACTORY
    quality: Annotated[dict[str, Any], Field(default_factory=dict)] = DEFAULT_FACTORY

    # lifecycle
    deprecated: datetime | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "example": {
                    "name": "patching",
                    "description": "example for service metadata db PATCH",
                    "thumbnail": "https://picsum.photos/200",
                    "icon": "https://picsum.photos/50",
                    "version_display": "S4L X",
                }
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


class ReleaseDBGet(BaseModel):
    version: ServiceVersion
    version_display: str | None
    deprecated: datetime | None
    created: datetime
    compatibility_policy: CompatiblePolicyDict | None


class ServiceWithHistoryDBGet(BaseModel):
    key: ServiceKey
    version: ServiceVersion
    # display
    name: str
    description: str
    description_ui: bool
    thumbnail: str | None
    icon: str | None
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
    history: list[ReleaseDBGet]


assert (  # nosec
    set(ReleaseDBGet.model_fields)
    .difference({"compatibility_policy"})
    .issubset(set(ServiceWithHistoryDBGet.model_fields))
)


class ServiceAccessRightsAtDB(ServiceKeyVersion, ServiceGroupAccessRights):
    gid: PositiveInt
    product_name: ProductName

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
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
        )

    model_config = ConfigDict(
        from_attributes=True, json_schema_extra=_update_json_schema_extra
    )
