from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class DatasetMetaData(BaseModel):
    id: str
    display_name: str


class FileMetaData(BaseModel):
    dataset_id: str
    package_id: str
    id: str
    name: str
    type: str
    path: Path
    size: int
    created_at: datetime
    last_modified_at: datetime
