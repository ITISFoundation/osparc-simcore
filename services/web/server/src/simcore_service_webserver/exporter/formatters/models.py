from datetime import datetime
from pathlib import Path

from models_library.projects import Project
from models_library.projects_nodes_io import LocationID, StorageFileID
from models_library.projects_state import ProjectStatus
from pydantic import AnyUrl, BaseModel, DirectoryPath, Field, validator

from .base_models import BaseLoadingModel

ShuffledData = dict[str, str]


class LinkAndPath2(BaseModel):
    # where all files are stored in the exported folder
    _FILES_DIRECTORY: str | Path = "storage"
    root_dir: DirectoryPath = Field(
        ...,
        description="temporary directory where all data is stored, to be ignored from serialization",
    )
    storage_type: LocationID = Field(
        ...,
        description="usually 0 for S3 or 1 for Pennsieve",
    )
    relative_path_to_file: StorageFileID = Field(
        ...,
        description="full path to where the file is going to be stored",
    )

    download_link: AnyUrl | None = Field(
        ..., description="Link from where to download the file"
    )

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
        return Path(f"{self.storage_type}") / self.relative_path_to_file

    @property
    def storage_path_to_file(self) -> Path:
        return self.root_dir / self._FILES_DIRECTORY / self.store_path

    async def is_file(self) -> bool:
        """Checks if the file was saved at the given link"""
        return self.storage_path_to_file.is_file()


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

    attachments: list[str] = Field(
        ..., description="list of paths for attachments found in the project directory"
    )

    @validator("version")
    @classmethod
    def _validate_version(cls, v):
        return str(v)


class ProjectFile(BaseLoadingModel, Project):
    _RELATIVE_STORAGE_PATH: str = "project.json"

    # migration validators --------------------------------
    # NOTE: these migration validator are necessary when the base Project class is modified
    # this allows importing an older project to the newest state
    _MIGRATION_FLAGS = dict(pre=True, always=True)

    @validator("state", **_MIGRATION_FLAGS)
    @classmethod
    def optional_project_state_added_locked_status(cls, v):
        """{"state":Optional[{"locked": {"value": bool}}}]
        -->
        {"state":Optional[{"locked": {"value": bool, "status": ProjectStatus}}}]"""

        # ProjectStatus is optional
        if v is not None:
            # get locked. old is {"locked": {"value": bool}}
            locked = v.get("locked")
            if not locked:
                raise ValueError(f"missing locked field in {v}")
            if not locked.get("status"):
                locked["status"] = ProjectStatus.CLOSED.value

        return v
