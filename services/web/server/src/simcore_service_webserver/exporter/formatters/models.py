import uuid

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Callable

import aiofiles
from pydantic import Field, validator, EmailStr, BaseModel

from .base_models import BaseLoadingModel
from ..file_response import makedirs

ShuffledData = Dict[str, str]


class LinkAndPath2(BaseModel):
    _FILES_DIRECTORY: str = "storage"  # where all files are stored
    root_dir: Path = Field(
        ...,
        description="temporary directory where all data is stored, to be ignored from serialization",
    )
    storage_type: str = Field(
        ...,
        description="usually 0 or 1 S3 or BlackFynn",
    )
    relative_path_to_file: Path = Field(
        ...,
        description="full path to where the file is going to be stored",
    )

    download_link: str = Field(..., description="Link from where to download the file")

    @validator("root_dir")
    @classmethod
    def _validate_root_dir(cls, v):
        if not isinstance(v, Path):
            v = Path(v)
        if not v.is_dir():
            raise ValueError(f"Provided path {str(v)} is not a directory!")
        return v

    @validator("relative_path_to_file")
    @classmethod
    def _validate_path_in_root_dir(cls, v):
        if not isinstance(v, Path):
            v = Path(v)
        if v.is_absolute():
            raise ValueError(f"Must provide a relative path, not {str(v)}")

        return v

    @property
    def store_path(self) -> Path:
        """Returns an absolute path to the file"""
        return Path(self.storage_type) / self.relative_path_to_file

    @property
    def storage_path_to_file(self) -> Path:
        return self.root_dir / self._FILES_DIRECTORY / self.store_path

    async def is_file(self) -> bool:
        """Checks if the file was saved at the given link"""
        return self.storage_path_to_file.is_file()

    def change_uuids_from_shuffled_data(self, shuffled_data: ShuffledData) -> None:
        """Change the files's project and workbench node based on provided data"""

    async def apply_shuffled_data(self, shuffled_data: ShuffledData) -> None:
        """Will replace paths on disk for the file and change the relative_path_to_file"""
        current_storage_path_to_file = self.storage_path_to_file
        relative_path_to_file_str = str(self.relative_path_to_file)
        for old_uuid, new_uuid in shuffled_data.items():
            relative_path_to_file_str = relative_path_to_file_str.replace(
                old_uuid, new_uuid
            )
        self.relative_path_to_file = Path(relative_path_to_file_str)

        # finally move file and check
        destination = self.storage_path_to_file
        await makedirs(destination.parent, exist_ok=True)
        await aiofiles.os.rename(current_storage_path_to_file, destination)


class Manifest(BaseLoadingModel):
    _STORAGE_PATH: str = "manifest.yaml"

    version: str = Field(
        ...,
        description=(
            "Version of the formatter used to export the study. This version should "
            "be also used for importing the study back"
        ),
    )

    creation_date_utc: datetime = Field(
        description="UTC date and time from when the project was exported",
        default_factory=datetime.utcnow,
    )

    attachments: List[str] = Field(
        ..., description="list of paths for attachments found in the project directory"
    )

    @validator("version")
    @classmethod
    def _validate_version(cls, v):
        return str(v)


class Project(BaseLoadingModel):
    _STORAGE_PATH: str = "project.yaml"

    name: str = Field(..., description="name of the study")
    description: str = Field(..., description="study description")
    uuid: str = Field(..., description="study unique id")
    last_change_date: datetime = Field(
        ..., alias="lastChangeDate", description="date when study was last changed"
    )
    creation_date: datetime = Field(
        ..., alias="creationDate", description="date when study was created"
    )
    project_owner: EmailStr = Field(
        ..., alias="prjOwner", description="email of the owner of the study"
    )
    thumbnail: str = Field(
        ..., description="contains a link to an image to be used as thumbnail"
    )
    ui: Dict[str, Any] = Field(..., description="contains data used to render the UI")
    workbench: Dict[str, Any] = Field(
        ...,
        description="representation all the information required to run and render studies",
    )

    def get_shuffled_uuids(self) -> ShuffledData:
        """
        Generates new uuid for the project_uuid and workbench nodes.
        NOTE: this function will not replace them.

        returns: new mapping from old to new to be applied to files
        """
        new_uuid: Callable = lambda: str(uuid.uuid4())

        uuid_replace_values: ShuffledData = {self.uuid: new_uuid()}

        for node in self.workbench.keys():
            uuid_replace_values[node] = new_uuid()

        return uuid_replace_values

    @classmethod
    def replace_via_serialization(
        cls, root_dir: Path, project: "Project", shuffled_data: ShuffledData
    ) -> "Project":
        serialized_project: str = project.storage_path.serialize(
            project.dict(exclude={"storage_path"}, by_alias=True)
        )

        for old_uuid, new_uuid in shuffled_data.items():
            serialized_project = serialized_project.replace(old_uuid, new_uuid)

        replaced_dict_data: Dict = project.storage_path.deserialize(serialized_project)
        replaced_dict_data["storage_path"] = dict(
            root_dir=root_dir, path_in_root_dir=cls._STORAGE_PATH
        )
        return Project.parse_obj(replaced_dict_data)