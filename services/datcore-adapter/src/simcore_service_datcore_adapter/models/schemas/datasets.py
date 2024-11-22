from datetime import datetime
from enum import Enum, unique
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class DatasetMetaData(BaseModel):
    id: str
    display_name: str


@unique
class DataType(str, Enum):
    FILE = "FILE"
    FOLDER = "FOLDER"


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
        cls, package: dict[str, Any], files: list[dict[str, Any]], base_path: Path
    ):
        """creates a FileMetaData from a pennsieve data structure."""
        pck_name: str = package["content"]["name"]
        if "extension" in package and not pck_name.endswith(package["extension"]):
            pck_name += ".".join((pck_name, package["extension"]))

        file_size = 0
        if package["content"]["packageType"] != "Collection" and files:
            file_size = files[0]["content"]["size"]

        return cls(
            dataset_id=package["content"]["datasetNodeId"],
            package_id=package["content"]["nodeId"],
            id=f"{package['content']['id']}",
            name=pck_name,
            path=base_path / pck_name,
            type=package["content"]["packageType"],
            size=file_size,
            created_at=package["content"]["createdAt"],
            last_modified_at=package["content"]["updatedAt"],
            data_type=(
                DataType.FOLDER
                if package["content"]["packageType"] == "Collection"
                else DataType.FILE
            ),
        )
