from typing import Optional

from models_library.services import (
    ServiceAccessRights,
    ServiceDockerData,
    ServiceMetaData,
)
from pydantic import EmailStr, Extra
from pydantic.main import BaseModel


# OpenAPI models (contain both service metadata and access rights)
class ServiceUpdate(ServiceMetaData, ServiceAccessRights):
    pass


class ServiceOut(
    ServiceDockerData, ServiceAccessRights, ServiceMetaData
):  # pylint: disable=too-many-ancestors
    owner: Optional[EmailStr]

    class Config:
        extra = Extra.ignore
        schema_extra = {
            "example": {
                "name": "File Picker",
                "thumbnail": None,
                "description": "File Picker",
                "classifiers": [],
                "quality": {},
                "access_rights": {
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
                        "name": "Odei Maiz",
                        "email": "maiz@itis.swiss",
                        "affiliation": None,
                    }
                ],
                "contact": "maiz@itis.swiss",
                "inputs": {},
                "outputs": {
                    "outFile": {
                        "displayOrder": 0,
                        "label": "File",
                        "description": "Chosen File",
                        "type": "data:*/*",
                        "fileToKeyMap": None,
                        "defaultValue": None,
                        "widget": None,
                    }
                },
                "owner": "maiz@itis.swiss",
            }
        }


# Items are non-detailed version of resources listed
class ServiceItem(BaseModel):
    class Config:
        extra = Extra.ignore
        schema_extra = {
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
