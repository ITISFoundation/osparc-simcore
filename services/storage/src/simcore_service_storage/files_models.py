"""
    Model schemas for storage's API
    Used in requests associated to the files resource
"""
from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class ApiResource(BaseModel):
    id: str

    # self url
    url: HttpUrl


class File(ApiResource):
    storage_source: str  # simcore/datcore/google drive etc
    title: Optional[str]


class FileEdit(File):
    # nothing is required
    pass


class FileList(BaseModel):
    items: List[File]
    # tokens ...
