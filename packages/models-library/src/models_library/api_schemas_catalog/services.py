from datetime import datetime
from typing import Any, TypeAlias

from models_library.rpc_pagination import PageRpc
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, NonNegativeInt

from ..boot_options import BootOptions
from ..emails import LowerCaseEmailStr
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
from ..users import GroupID
from ..utils.change_case import snake_to_camel


class ServiceUpdate(ServiceMetaDataEditable, ServiceAccessRights):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                # ServiceAccessRights
                "accessRights": {
                    1: {
                        "execute_access": False,
                        "write_access": False,
                    },  # type: ignore[dict-item]
                    2: {
                        "execute_access": True,
                        "write_access": True,
                    },  # type: ignore[dict-item]
                    44: {
                        "execute_access": False,
                        "write_access": False,
                    },  # type: ignore[dict-item]
                },
                # ServiceMetaData = ServiceCommonData +
                "name": "My Human Readable Service Name",
                "thumbnail": None,
                "description": "An interesting service that does something",
                "classifiers": ["RRID:SCR_018997", "RRID:SCR_019001"],
                "quality": {
                    "tsr": {
                        "r01": {"level": 3, "references": ""},
                        "r02": {"level": 2, "references": ""},
                        "r03": {"level": 0, "references": ""},
                        "r04": {"level": 0, "references": ""},
                        "r05": {"level": 2, "references": ""},
                        "r06": {"level": 0, "references": ""},
                        "r07": {"level": 0, "references": ""},
                        "r08": {"level": 1, "references": ""},
                        "r09": {"level": 0, "references": ""},
                        "r10": {"level": 0, "references": ""},
                    },
                    "enabled": True,
                    "annotations": {
                        "vandv": "",
                        "purpose": "",
                        "standards": "",
                        "limitations": "",
                        "documentation": "",
                        "certificationLink": "",
                        "certificationStatus": "Uncertified",
                    },
                },
            }
        }
    )


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
    owner: LowerCaseEmailStr | None = Field(
        description="None when the owner email cannot be found in the database"
    )

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra={"examples": [_EXAMPLE_FILEPICKER, _EXAMPLE_SLEEPER]},
    )


class ServiceGetV2(BaseModel):
    key: ServiceKey
    version: ServiceVersion

    name: str
    thumbnail: HttpUrl | None = None
    description: str

    description_ui: bool = False

    version_display: str | None = None

    service_type: ServiceType = Field(default=..., alias="type")

    contact: LowerCaseEmailStr | None
    authors: list[Author] = Field(..., min_length=1)
    owner: LowerCaseEmailStr | None = Field(
        description="None when the owner email cannot be found in the database"
    )

    inputs: ServiceInputsDict
    outputs: ServiceOutputsDict

    boot_options: BootOptions | None = None
    min_visible_inputs: NonNegativeInt | None = None

    access_rights: dict[GroupID, ServiceGroupAccessRightsV2] | None

    classifiers: list[str] | None = []
    quality: dict[str, Any] = {}

    history: list[ServiceRelease] = Field(
        default_factory=list,
        description="history of releases for this service at this point in time, starting from the newest to the oldest."
        " It includes current release.",
        json_schema_extra={"default": []},
    )

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=snake_to_camel,
        json_schema_extra={
            "examples": [
                {
                    **_EXAMPLE_SLEEPER,  # v2.2.1  (latest)
                    "history": [
                        {
                            "version": _EXAMPLE_SLEEPER["version"],
                            "version_display": "Summer Release",
                            "released": "2024-07-20T15:00:00",
                        },
                        {
                            "version": "2.0.0",
                            "compatibility": {
                                "canUpdateTo": {"version": _EXAMPLE_SLEEPER["version"]},
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
                            "retired": "2024-07-20T15:00:00",
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
        },
    )


PageRpcServicesGetV2: TypeAlias = PageRpc[
    # WARNING: keep this definition in models_library and not in the RPC interface
    ServiceGetV2
]

ServiceResourcesGet: TypeAlias = ServiceResourcesDict


class ServiceUpdateV2(BaseModel):
    name: str | None = None
    thumbnail: HttpUrl | None = None

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
