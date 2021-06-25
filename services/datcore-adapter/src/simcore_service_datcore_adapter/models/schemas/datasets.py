from datetime import datetime
from enum import Enum, unique
from pathlib import Path

import pennsieve
from pydantic import BaseModel


class DatasetMetaData(BaseModel):
    id: str
    display_name: str


@unique
class DataType(str, Enum):
    FILE = "FILE"
    FOLDER = "FOLDER"


def compute_full_path(
    ps: pennsieve.Pennsieve, package: pennsieve.models.BaseDataNode
) -> Path:
    dataset_path = Path(ps.get_dataset(package.dataset).name)

    def _get_full_path(pck: pennsieve.models.BaseDataNode) -> Path:
        path = Path(pck.name)
        if pck.type != "Collection":
            path = Path(pck.s3_key).name
        if pck.parent:
            path = _get_full_path(ps.get(pck.parent)) / path
        return path

    return dataset_path / _get_full_path(package)


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
    data_type: DataType

    @classmethod
    def from_pennsieve_package(
        cls, ps: pennsieve.Pennsieve, package: pennsieve.models.BaseDataNode
    ):
        return cls(
            dataset_id=package.dataset,
            package_id=package.id,
            id=package.id,
            name=package.name,
            path=compute_full_path(ps, package),
            type=package.type,
            size=-1 if package.type == "Collection" else package.files[0].size,
            created_at=package.created_at,
            last_modified_at=package.updated_at,
            data_type=DataType.FOLDER
            if package.type == "Collection"
            else DataType.FILE,
        )
