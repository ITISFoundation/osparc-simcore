from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from pydantic import Field, validator, EmailStr, BaseModel

from .base_models import BaseLoadingModel

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
        return (
            self.root_dir
            / self._FILES_DIRECTORY
            / self.storage_type
            / self.relative_path_to_file
        )

    async def is_file(self) -> bool:
        """Checks if the file was saved at the given link"""
        return self.store_path.is_file()

    def change_uuids_from_shuffled_data(self, shuffled_data: ShuffledData) -> None:
        """Change the files's project and workbench node based on provided data"""


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

    def shuffle_uuids(self) -> ShuffledData:
        """
        Changes the project.uuid and all uuids of the nodes in the workbench.
        Allows for multiple imports of the project.

        returns: new mapping from old to new to be applied to files
        """