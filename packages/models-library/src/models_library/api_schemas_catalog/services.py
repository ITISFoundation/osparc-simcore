from typing import Any, ClassVar

from pydantic import Extra
from pydantic.main import BaseModel

from ..emails import LowerCaseEmailStr
from ..services import ServiceDockerData, ServiceMetaData
from ..services_access import ServiceAccessRights
from ..services_resources import ServiceResourcesDict


# OpenAPI models (contain both service metadata and access rights)
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
                "description": "File Picker",
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


# TODO: prototype for next iteration
# Items are non-detailed version of resources listed
class ServiceItem(BaseModel):
    class Config:
        extra = Extra.ignore
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "title": "File Picker",  # NEW: rename 'name' as title (so it is not confused with an identifier!)
                "thumbnail": None,  # optional
                "description": "File Picker",
                "classifiers_url": "https://catalog:8080/services/a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4/classifiers",
                "quality": "https://catalog:8080/services/a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4/quality",
                "access_rights_url": "https://catalog:8080/services/a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4/access_rights",
                "key_id": "simcore/services/frontend/file-picker",  # NEW: renames key -> key_id
                "version": "1.0.0",
                "id": "a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4",  # NEW: alternative identifier to key_id:version
                "integration-version": "1.0.0",
                "type": "dynamic",
                "badges_url": "https://catalog:8080/services/a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4/badges",
                "authors_url": "https://catalog:8080/services/a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4/authors",
                "inputs_url": "https://catalog:8080/services/a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4/inputs",
                "outputs_url": "https://catalog:8080/services/a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4/outputs",
                "owner": "maiz@itis.swiss",  #  NEW, replaces "contact": "maiz@itis.swiss"
                "url": "https://catalog:8080/services/a8f5a503-01d5-40bc-b416-f5b7cc5d1fa4",  # NEW self
            }
        }


ServiceResourcesGet = ServiceResourcesDict
