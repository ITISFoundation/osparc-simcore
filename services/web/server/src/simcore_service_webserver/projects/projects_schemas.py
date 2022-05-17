""" Models for project's in webserver's rest API

These models are used for request bodies and response payloads of operations on the project resource.

"""
from typing import Optional

import orjson
from models_library.projects_access import AccessRights, GroupIDStr
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, EmailStr, Extra, Field, HttpUrl
from servicelib.json_serialization import json_dumps


class ProjectCreate(BaseModel):
    """
        -> POST /projects (ProjectCreate)

    - resource ID (i.e. project's uuid) is defined in the *backend* on creation

    """

    name: str
    description: str
    thumbnail: Optional[HttpUrl] = None

    # TODO: why these are necessary?
    prj_owner: EmailStr = Field(..., description="user's email of owner")
    access_rights: dict[GroupIDStr, AccessRights] = Field(...)

    class Config:
        extra = Extra.ignore  # error tolerant
        alias_generator = snake_to_camel
        json_loads = orjson.loads
        json_dumps = json_dumps


class ProjectGet(BaseModel):
    name: str
    description: str
    thumbnail: HttpUrl = ""
    prj_owner: EmailStr = Field(..., description="user's email of owner")
    access_rights: dict[GroupIDStr, AccessRights] = Field(...)

    class Config:
        extra = Extra.allow
        alias_generator = snake_to_camel
        json_dumps = json_dumps
