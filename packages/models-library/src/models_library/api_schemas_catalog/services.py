from typing import Any, ClassVar

from pydantic import Extra

from ..emails import LowerCaseEmailStr
from ..services import ServiceDockerData, ServiceMetaData
from ..services_access import ServiceAccessRights
from ..services_resources import ServiceResourcesDict


class ServiceUpdate(ServiceMetaData, ServiceAccessRights):
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


class ServiceGet(
    ServiceDockerData, ServiceAccessRights, ServiceMetaData
):  # pylint: disable=too-many-ancestors
    owner: LowerCaseEmailStr | None

    class Config:
        allow_population_by_field_name = True
        extra = Extra.ignore
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
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
        }


ServiceResourcesGet = ServiceResourcesDict
