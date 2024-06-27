from typing import Any, ClassVar

from models_library.services_history import ServiceRelease
from pydantic import Extra, Field

from ..emails import LowerCaseEmailStr
from ..services import ServiceMetaDataPublished
from ..services_access import ServiceAccessRights
from ..services_metadata_editable import ServiceMetaDataEditable
from ..services_resources import ServiceResourcesDict


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
    "integration-version": None,
    "type": "dynamic",
    "badges": None,
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
    "integration-version": "1.0.0",
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
            "keyId": "input_1",
        },
        "input_2": {
            "unitLong": "second",
            "unitShort": "s",
            "label": "Sleep interval",
            "description": "Choose an amount of time to sleep in range [0:]",
            "keyId": "input_2",
            "displayOrder": 2,
            "type": "ref_contentSchema",
            "contentSchema": {
                "title": "Sleep interval",
                "type": "integer",
                "x_unit": "second",
                "minimum": 0,
            },
            "defaultValue": 2,
        },
        "input_3": {
            "displayOrder": 3,
            "label": "Fail after sleep",
            "description": "If set to true will cause service to fail after it sleeps",
            "type": "boolean",
            "defaultValue": False,
            "keyId": "input_3",
        },
        "input_4": {
            "unitLong": "meter",
            "unitShort": "m",
            "label": "Distance to bed",
            "description": "It will first walk the distance to bed",
            "keyId": "input_4",
            "displayOrder": 4,
            "type": "ref_contentSchema",
            "contentSchema": {
                "title": "Distance to bed",
                "type": "integer",
                "x_unit": "meter",
            },
            "defaultValue": 0,
        },
        "input_5": {
            "unitLong": "byte",
            "unitShort": "B",
            "label": "Dream (or nightmare) of the night",
            "description": "Defines the size of the dream that will be generated [0:]",
            "keyId": "input_5",
            "displayOrder": 5,
            "type": "ref_contentSchema",
            "contentSchema": {
                "title": "Dream of the night",
                "type": "integer",
                "x_unit": "byte",
                "minimum": 0,
            },
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
            "keyId": "output_1",
        },
        "output_2": {
            "unitLong": "second",
            "unitShort": "s",
            "label": "Random sleep interval",
            "description": "Interval is generated in range [1-9]",
            "keyId": "output_2",
            "displayOrder": 2,
            "type": "ref_contentSchema",
            "contentSchema": {
                "title": "Random sleep interval",
                "type": "integer",
                "x_unit": "second",
            },
        },
        "output_3": {
            "displayOrder": 3,
            "label": "Dream output",
            "description": "Contains some random data representing a dream",
            "type": "data:text/plain",
            "fileToKeyMap": {"dream.txt": "output_3"},
            "keyId": "output_3",
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
        schema_extra: ClassVar[dict[str, Any]] = {"example": _EXAMPLE_FILEPICKER}


class DEVServiceGet(ServiceGet):
    # pylint: disable=too-many-ancestors

    history: list[ServiceRelease] = Field(
        default=[],
        description="history of releases for this service at this point in time, starting from the newest to the oldest."
        " It includes current release.",
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    **_EXAMPLE_SLEEPER,  # v2.2.1  (latest)
                    "history": [
                        {
                            "version": _EXAMPLE_SLEEPER["version"],
                            "version_display": "Summer Release",
                            "release_date": "2024-07-20T15:00:00",
                        },
                        {
                            "version": "2.0.0",
                            "compatibility": {
                                "can_update_to": _EXAMPLE_SLEEPER["version"],
                            },
                        },
                        {"version": "0.9.11"},
                        {"version": "0.9.10"},
                        {
                            "version": "0.9.8",
                            "compatibility": {
                                "can_update_to": "0.9.11",
                            },
                        },
                        {
                            "version": "0.9.1",
                            "version_display": "Matterhorn",
                            "release_date": "2024-01-20T18:49:17",
                            "compatibility": {
                                "can_update_to": "0.9.11",
                            },
                        },
                        {"version": "0.9.0"},
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
                            "release_date": "2025-03-25T00:00:00",
                        }
                    ],
                },
            ]
        }


ServiceResourcesGet = ServiceResourcesDict
