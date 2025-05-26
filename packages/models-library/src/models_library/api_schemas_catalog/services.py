from datetime import datetime
from typing import Annotated, Any, TypeAlias

from common_library.basic_types import DEFAULT_FACTORY
from models_library.rpc_pagination import PageRpc
from pydantic import ConfigDict, Field, HttpUrl, NonNegativeInt
from pydantic.config import JsonDict

from ..boot_options import BootOptions
from ..emails import LowerCaseEmailStr
from ..groups import GroupID
from ..rest_filters import Filters
from ..services_access import ServiceAccessRights, ServiceGroupAccessRightsV2
from ..services_authoring import Author
from ..services_enums import ServiceType
from ..services_history import ServiceRelease
from ..services_metadata_editable import ServiceMetaDataEditable
from ..services_metadata_published import (
    ServiceInputsDict,
    ServiceMetaDataPublished,
    ServiceOutputsDict,
)
from ..services_resources import ServiceResourcesDict
from ..services_types import ServiceKey, ServiceVersion
from ..utils.change_case import snake_to_camel
from ._base import CatalogInputSchema, CatalogOutputSchema

_EXAMPLE_FILEPICKER: dict[str, Any] = {
    "name": "File Picker",
    "thumbnail": None,
    "description": "description",
    "classifiers": [],
    "quality": {},
    "accessRights": {
        "1": {"execute_access": True, "write_access": False},
        "4": {"execute_access": True, "write_access": True},
    },
    "key": "simcore/services/frontend/file-picker",
    "version": "1.0.0",
    "type": "dynamic",
    "authors": [
        {
            "name": "Red Pandas",
            "email": "redpandas@wonderland.com",
            "affiliation": None,
        }
    ],
    "contact": "redpandas@wonderland.com",
    "inputs": {},
    "outputs": {
        "outFile": {
            "displayOrder": 0,
            "label": "File",
            "description": "Chosen File",
            "type": "data:*/*",
            "fileToKeyMap": None,
            "widget": None,
        }
    },
    "owner": "redpandas@wonderland.com",
}

_EXAMPLE_FILEPICKER_V2 = {
    **_EXAMPLE_FILEPICKER,
    "accessRights": {
        "1": {"execute": True, "write": False},
        "4": {"execute": True, "write": True},
    },
}


_EXAMPLE_SLEEPER: dict[str, Any] = {
    "name": "sleeper",
    "thumbnail": None,
    "description": "A service which awaits for time to pass, two times.",
    "description_ui": True,
    "icon": "https://cdn-icons-png.flaticon.com/512/25/25231.png",
    "classifiers": [],
    "quality": {},
    "accessRights": {"1": {"execute": True, "write": False}},
    "key": "simcore/services/comp/itis/sleeper",
    "version": "2.2.1",
    "version_display": "2 Xtreme",
    "type": "computational",
    "authors": [
        {
            "name": "Author Bar",
            "email": "author@acme.com",
            "affiliation": "ACME",
        },
    ],
    "contact": "contact@acme.com",
    "inputs": {
        "input_1": {
            "displayOrder": 1,
            "label": "File with int number",
            "description": "Pick a file containing only one integer",
            "type": "data:text/plain",
            "fileToKeyMap": {"single_number.txt": "input_1"},
        },
        "input_2": {
            "label": "Sleep interval",
            "description": "Choose an amount of time to sleep in range [0:]",
            "displayOrder": 2,
            "type": "integer",
            "defaultValue": 2,
        },
        "input_3": {
            "displayOrder": 3,
            "label": "Fail after sleep",
            "description": "If set to true will cause service to fail after it sleeps",
            "type": "boolean",
            "defaultValue": False,
        },
        "input_4": {
            "label": "Distance to bed",
            "description": "It will first walk the distance to bed",
            "displayOrder": 4,
            "type": "integer",
            "defaultValue": 0,
        },
        "input_5": {
            "label": "Dream (or nightmare) of the night",
            "description": "Defines the size of the dream that will be generated [0:]",
            "displayOrder": 5,
            "type": "integer",
            "defaultValue": 0,
        },
    },
    "outputs": {
        "output_1": {
            "displayOrder": 1,
            "label": "File containing one random integer",
            "description": "Integer is generated in range [1-9]",
            "type": "data:text/plain",
            "fileToKeyMap": {"single_number.txt": "output_1"},
        },
        "output_2": {
            "label": "Random sleep interval",
            "description": "Interval is generated in range [1-9]",
            "displayOrder": 2,
            "type": "integer",
        },
        "output_3": {
            "displayOrder": 3,
            "label": "Dream output",
            "description": "Contains some random data representing a dream",
            "type": "data:text/plain",
            "fileToKeyMap": {"dream.txt": "output_3"},
        },
    },
    "owner": "owner@acme.com",
}


class ServiceGet(
    ServiceMetaDataPublished, ServiceAccessRights, ServiceMetaDataEditable
):  # pylint: disable=too-many-ancestors
    owner: Annotated[
        LowerCaseEmailStr | None,
        Field(description="None when the owner email cannot be found in the database"),
    ]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update({"examples": [_EXAMPLE_FILEPICKER, _EXAMPLE_SLEEPER]})

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra=_update_json_schema_extra,
    )


class ServiceSummary(CatalogOutputSchema):
    key: ServiceKey
    version: ServiceVersion
    name: str
    description: str
    version_display: str | None = None
    contact: LowerCaseEmailStr | None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "key": _EXAMPLE_SLEEPER["key"],
                        "version": _EXAMPLE_SLEEPER["version"],
                        "name": _EXAMPLE_SLEEPER["name"],
                        "description": _EXAMPLE_SLEEPER["description"],
                        "version_display": _EXAMPLE_SLEEPER["version_display"],
                        "contact": _EXAMPLE_SLEEPER["contact"],
                    },
                    {
                        "key": _EXAMPLE_SLEEPER["key"],
                        "version": "100.0.0",
                        "name": "sleeper",
                        "description": "short description",
                        "version_display": "HUGE Release",
                        "contact": "contact@acme.com",
                    },
                    {
                        "key": _EXAMPLE_FILEPICKER["key"],
                        "version": _EXAMPLE_FILEPICKER["version"],
                        "name": _EXAMPLE_FILEPICKER["name"],
                        "description": _EXAMPLE_FILEPICKER["description"],
                        "version_display": None,
                        "contact": _EXAMPLE_FILEPICKER["contact"],
                    },
                ]
            }
        )

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        alias_generator=snake_to_camel,
        json_schema_extra=_update_json_schema_extra,
    )


class _BaseServiceGetV2(ServiceSummary):
    service_type: Annotated[ServiceType, Field(alias="type")]

    thumbnail: HttpUrl | None = None
    icon: HttpUrl | None = None

    description_ui: bool = False

    authors: Annotated[list[Author], Field(min_length=1)]
    owner: Annotated[
        LowerCaseEmailStr | None,
        Field(description="None when the owner email cannot be found in the database"),
    ]

    inputs: ServiceInputsDict
    outputs: ServiceOutputsDict

    boot_options: BootOptions | None = None
    min_visible_inputs: NonNegativeInt | None = None

    access_rights: dict[GroupID, ServiceGroupAccessRightsV2] | None

    classifiers: Annotated[
        list[str] | None,
        Field(default_factory=list),
    ] = DEFAULT_FACTORY

    quality: Annotated[
        dict[str, Any],
        Field(default_factory=dict),
    ] = DEFAULT_FACTORY

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=snake_to_camel,
        json_schema_extra={"example": _EXAMPLE_SLEEPER},
    )


class LatestServiceGet(_BaseServiceGetV2):
    release: Annotated[
        ServiceRelease,
        Field(description="release information of current (latest) service"),
    ]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        **_EXAMPLE_SLEEPER,  # v2.2.1  (latest)
                        "release": {
                            "version": _EXAMPLE_SLEEPER["version"],
                            "version_display": "Summer Release",
                            "released": "2025-07-20T15:00:00",
                        },
                    }
                ]
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )


class ServiceGetV2(_BaseServiceGetV2):
    history: Annotated[
        list[ServiceRelease],
        Field(
            default_factory=list,
            description="history of releases for this service at this point in time, starting from the newest to the oldest."
            " It includes current release.",
            json_schema_extra={"default": []},
        ),
    ] = DEFAULT_FACTORY

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        **_EXAMPLE_SLEEPER,  # v2.2.1  (latest)
                        "history": [
                            {
                                "version": _EXAMPLE_SLEEPER["version"],
                                "version_display": "Summer Release",
                                "released": "2024-07-21T15:00:00",
                            },
                            {
                                "version": "2.0.0",
                                "compatibility": {
                                    "canUpdateTo": {
                                        "version": _EXAMPLE_SLEEPER["version"]
                                    },
                                },
                            },
                            {"version": "0.9.11"},
                            {"version": "0.9.10"},
                            {
                                "version": "0.9.8",
                                "compatibility": {
                                    "canUpdateTo": {"version": "0.9.11"},
                                },
                            },
                            {
                                "version": "0.9.1",
                                "versionDisplay": "Matterhorn",
                                "released": "2024-01-20T18:49:17",
                                "compatibility": {
                                    "can_update_to": {"version": "0.9.11"},
                                },
                            },
                            {
                                "version": "0.9.0",
                                "retired": "2024-07-20T16:00:00",
                            },
                            {"version": "0.8.0"},
                            {"version": "0.1.0"},
                        ],
                    },
                    {
                        **_EXAMPLE_FILEPICKER_V2,
                        "history": [
                            {
                                "version": _EXAMPLE_FILEPICKER_V2["version"],
                                "version_display": "Odei Release",
                                "released": "2025-03-25T00:00:00",
                            }
                        ],
                    },
                ]
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )


PageRpcLatestServiceGet: TypeAlias = PageRpc[
    # WARNING: keep this definition in models_library and not in the RPC interface
    # otherwise the metaclass PageRpc[*] will create *different* classes in server/client side
    # and will fail to serialize/deserialize these parameters when transmitted/received
    LatestServiceGet
]

PageRpcServiceRelease: TypeAlias = PageRpc[
    # WARNING: keep this definition in models_library and not in the RPC interface
    # otherwise the metaclass PageRpc[*] will create *different* classes in server/client side
    # and will fail to serialize/deserialize these parameters when transmitted/received
    ServiceRelease
]

# Create PageRpc types
PageRpcServiceSummary = PageRpc[ServiceSummary]

ServiceResourcesGet: TypeAlias = ServiceResourcesDict


class ServiceUpdateV2(CatalogInputSchema):
    name: str | None = None
    thumbnail: HttpUrl | None = None
    icon: HttpUrl | None = None

    description: str | None = None
    description_ui: bool = False
    version_display: str | None = None

    deprecated: datetime | None = None

    classifiers: list[str] | None = None
    quality: dict[str, Any] = {}

    access_rights: dict[GroupID, ServiceGroupAccessRightsV2] | None = None

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=snake_to_camel,
    )


assert set(ServiceUpdateV2.model_fields.keys()) - set(  # nosec
    ServiceGetV2.model_fields.keys()
) == {"deprecated"}


class MyServiceGet(CatalogOutputSchema):
    key: ServiceKey
    release: ServiceRelease

    owner: GroupID | None
    my_access_rights: ServiceGroupAccessRightsV2


class ServiceListFilters(Filters):
    service_type: Annotated[
        ServiceType | None,
        Field(
            description="Filter only services of a given type. If None, then all types are returned"
        ),
    ] = None

    service_key_pattern: Annotated[
        str | None,
        Field(
            description="Filter services by key pattern (e.g. 'simcore/services/comp/itis/*')",
        ),
    ] = None

    version_display_pattern: Annotated[
        str | None,
        Field(
            description="Filter services by version display pattern (e.g. '*2023*')",
        ),
    ] = None


__all__: tuple[str, ...] = ("ServiceRelease",)
