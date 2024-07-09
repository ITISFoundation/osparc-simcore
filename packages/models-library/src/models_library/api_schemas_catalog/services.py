from typing import Any, ClassVar, TypeAlias

from models_library.rpc_pagination import PageRpc
from pydantic import BaseModel, Extra, Field, HttpUrl, NonNegativeInt

from ..boot_options import BootOptions
from ..emails import LowerCaseEmailStr
from ..services_access import ServiceAccessRights
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
    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                # ServiceAccessRights
                "accessRights": {
                    1: {
                        "execute_access": False,
                        "write_access": False,
                    },
                    2: {
                        "execute_access": True,
                        "write_access": True,
                    },
                    44: {
                        "execute_access": False,
                        "write_access": False,
                    },
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


_EXAMPLE_SLEEPER: dict[str, Any] = {
    "name": "sleeper",
    "thumbnail": None,
    "description": "A service which awaits for time to pass, two times.",
    "classifiers": [],
    "quality": {},
    "accessRights": {"1": {"execute_access": True, "write_access": False}},
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
    owner: LowerCaseEmailStr | None

    class Config:
        allow_population_by_field_name = True
        extra = Extra.ignore
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [_EXAMPLE_FILEPICKER, _EXAMPLE_SLEEPER]
        }


class ServiceGroupAccessRightsV2(BaseModel):
    execute: bool = False
    write: bool = False

    class Config:
        alias_generator = snake_to_camel
        allow_population_by_field_name = True


class ServiceGetV2(BaseModel):
    key: ServiceKey
    version: ServiceVersion

    name: str
    thumbnail: HttpUrl | None = None
    description: str

    version_display: str | None = None

    service_type: ServiceType = Field(default=..., alias="type")

    contact: LowerCaseEmailStr | None
    authors: list[Author] = Field(..., min_items=1)
    owner: LowerCaseEmailStr | None

    inputs: ServiceInputsDict
    outputs: ServiceOutputsDict

    boot_options: BootOptions | None = None
    min_visible_inputs: NonNegativeInt | None = None

    access_rights: dict[GroupID, ServiceGroupAccessRightsV2] | None

    classifiers: list[str] | None = None
    quality: dict[str, Any] = {}

    history: list[ServiceRelease] = Field(
        default=[],
        description="history of releases for this service at this point in time, starting from the newest to the oldest."
        " It includes current release.",
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        allow_population_by_field_name = True
        schema_extra: ClassVar[dict[str, Any]] = {
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
                                "canUpdateTo": _EXAMPLE_SLEEPER["version"],
                            },
                        },
                        {"version": "0.9.11"},
                        {"version": "0.9.10"},
                        {
                            "version": "0.9.8",
                            "compatibility": {
                                "canUpdateTo": "0.9.11",
                            },
                        },
                        {
                            "version": "0.9.1",
                            "versionDisplay": "Matterhorn",
                            "released": "2024-01-20T18:49:17",
                            "compatibility": {
                                "can_update_to": "0.9.11",
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
                    **_EXAMPLE_FILEPICKER,
                    "history": [
                        {
                            "version": _EXAMPLE_FILEPICKER["version"],
                            "version_display": "Odei Release",
                            "released": "2025-03-25T00:00:00",
                        }
                    ],
                },
            ]
        }


PageRpcServicesGetV2: TypeAlias = PageRpc[
    # WARNING: keep this definition in models_library and not in the RPC interface
    ServiceGetV2
]

ServiceResourcesGet: TypeAlias = ServiceResourcesDict
