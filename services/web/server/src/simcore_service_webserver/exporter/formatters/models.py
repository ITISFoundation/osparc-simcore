import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Union

import aiofiles
from models_library.projects import Project
from pydantic import BaseModel, DirectoryPath, Field, validator

from ..utils import makedirs
from .base_models import BaseLoadingModel

ShuffledData = Dict[str, str]


class LinkAndPath2(BaseModel):
    # where all files are stored in the exported folder
    _FILES_DIRECTORY: Union[str, Path] = "storage"
    root_dir: DirectoryPath = Field(
        ...,
        description="temporary directory where all data is stored, to be ignored from serialization",
    )
    storage_type: str = Field(
        ...,
        description="usually 0 for S3 or 1 for BlackFynn",
    )
    relative_path_to_file: Path = Field(
        ...,
        description="full path to where the file is going to be stored",
    )

    download_link: str = Field(..., description="Link from where to download the file")

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

    async def apply_shuffled_data(self, shuffled_data: ShuffledData) -> None:
        """Will replace paths on disk for the file and change the relative_path_to_file"""
        current_storage_path_to_file = self.storage_path_to_file
        relative_path_to_file_str = str(self.relative_path_to_file)
        for old_uuid, new_uuid in shuffled_data.items():
            relative_path_to_file_str = relative_path_to_file_str.replace(
                old_uuid, new_uuid
            )
        self.relative_path_to_file = Path(relative_path_to_file_str)

        # finally move file to new target path
        destination = self.storage_path_to_file
        await makedirs(destination.parent, exist_ok=True)
        await aiofiles.os.rename(current_storage_path_to_file, destination)


class ManifestFile(BaseLoadingModel):
    _RELATIVE_STORAGE_PATH: str = "manifest.json"

    version: str = Field(
        ...,
        description=(
            "Version of the formatter used to export the study. This version is "
            "also used for importing the study back and autodetected. "
            "WARNING: never change this field's name."
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


class ProjectFile(BaseLoadingModel, Project):
    _RELATIVE_STORAGE_PATH: str = "project.json"

    def get_shuffled_uuids(self) -> ShuffledData:
        """
        Generates new uuid for the project_uuid and workbench nodes.
        This is the more portable and secure way for shuffling uuids.
        NOTE: this function will not replace them.

        returns: new mapping from old to new to be applied to files
        """
        new_uuid: Callable = lambda: str(uuid.uuid4())

        uuid_replace_values: ShuffledData = {str(self.uuid): new_uuid()}

        for node in self.workbench.keys():
            uuid_replace_values[node] = new_uuid()

        return uuid_replace_values

    def new_instance_from_shuffled_data(
        self, shuffled_data: ShuffledData
    ) -> "ProjectFile":
        project_as_string = self.json(
            exclude={"storage_path"}, by_alias=True, exclude_unset=True
        )

        for old_uuid, new_uuid in shuffled_data.items():
            project_as_string = project_as_string.replace(old_uuid, new_uuid)

        new_obj = ProjectFile.parse_raw(project_as_string)
        new_obj.storage_path = self.storage_path

        return new_obj
