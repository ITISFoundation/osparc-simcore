from datetime import datetime
from typing import Annotated, Any

from common_library.basic_types import DEFAULT_FACTORY
from models_library.basic_types import IdInt
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.rest_filters import Filters
from models_library.services_access import ServiceGroupAccessRights
from models_library.services_base import ServiceKeyVersion
from models_library.services_enums import ServiceType
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.utils.common_validators import empty_str_to_none_pre_validator
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)
from pydantic.config import JsonDict
from simcore_postgres_database.models.services_compatibility import CompatiblePolicyDict


class ServiceMetaDataDBGet(BaseModel):
    # primary-keys
    key: ServiceKey
    version: ServiceVersion

    # ownership
    owner: GroupID | None

    # display
    name: str
    description: str
    description_ui: bool
    thumbnail: str | None
    icon: str | None
    version_display: str | None

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


def _httpurl_to_str(value: HttpUrl | str | None) -> str | None:
    if isinstance(value, HttpUrl):
        return f"{value}"
    return value


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
    icon: Annotated[str | None, BeforeValidator(_httpurl_to_str)] = None
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

    _prevent_empty_strings_in_nullable_string_cols = field_validator(
        "icon", "thumbnail", "version_display", mode="before"
    )(empty_str_to_none_pre_validator)


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

    _prevent_empty_strings_in_nullable_string_cols = field_validator(
        "icon", "thumbnail", "version_display", mode="before"
    )(empty_str_to_none_pre_validator)


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
    gid: GroupID
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


class ServiceFiltersDB(Filters):
    service_type: ServiceType | None = None
    service_key_pattern: str | None = None
    version_display_pattern: str | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "example": {
                    "service_type": "computational",
                }
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)
