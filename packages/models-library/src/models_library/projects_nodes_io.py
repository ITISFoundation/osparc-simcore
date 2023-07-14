"""
    Link models used at i/o port nodes:
        - Link to files:
            - Generic: DownloadLink
            - At Custom Service: SimCoreFileLink, DatCoreFileLink
        - Link to another port: PortLink
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, TypeAlias
from uuid import UUID

from pydantic import (
    AnyUrl,
    BaseModel,
    ConstrainedStr,
    Extra,
    Field,
    parse_obj_as,
    validator,
)

from .basic_regex import (
    DATCORE_FILE_ID_RE,
    SIMCORE_S3_DIRECTORY_ID_RE,
    SIMCORE_S3_FILE_ID_RE,
    UUID_RE,
)
from .services import PROPERTY_KEY_RE

if TYPE_CHECKING:
    pass

NodeID = UUID


class UUIDStr(ConstrainedStr):
    regex: re.Pattern[str] | None = re.compile(UUID_RE)


NodeIDStr = UUIDStr

LocationID = int
LocationName = str


class SimcoreS3FileID(ConstrainedStr):
    regex: re.Pattern[str] | None = re.compile(SIMCORE_S3_FILE_ID_RE)


class SimcoreS3DirectoryID(ConstrainedStr):
    """
    A simcore directory has the following structure:
        `{project_id}/{node_id}/simcore-dir-name/`
    """

    regex: re.Pattern[str] | None = re.compile(SIMCORE_S3_DIRECTORY_ID_RE)

    @staticmethod
    def _get_parent(s3_object: str, *, parent_index: int) -> str:
        # NOTE: s3_object, sometimes is a directory, in that case
        # append a fake file so that the parent count still works
        if s3_object.endswith("/"):
            s3_object += "__placeholder_file_when_s3_object_is_a_directory__"

        parents: list[Path] = list(Path(s3_object).parents)
        try:
            return f"{parents[-parent_index]}"
        except IndexError as err:
            msg = (
                f"'{s3_object}' does not have enough parents, "
                f"expected {parent_index} found {parents}"
            )
            raise ValueError(msg) from err

    @classmethod
    def validate(cls, value: str) -> str:
        value = super().validate(value)
        value = value.rstrip("/")
        parent = cls._get_parent(value, parent_index=3)

        directory_candidate = value.strip(parent)
        if "/" in directory_candidate:
            msg = f"Not allowed subdirectory found in '{directory_candidate}'"
            raise ValueError(msg)
        return f"{value}/"

    @classmethod
    def from_simcore_s3_object(cls, s3_object: str) -> "SimcoreS3DirectoryID":
        parent_path: str = cls._get_parent(s3_object, parent_index=4)
        return parse_obj_as(cls, f"{parent_path}/")


class DatCoreFileID(ConstrainedStr):
    regex: re.Pattern[str] | None = re.compile(DATCORE_FILE_ID_RE)


StorageFileID: TypeAlias = SimcoreS3FileID | DatCoreFileID


class PortLink(BaseModel):
    """I/O port type to reference to an output port of another node in the same project"""

    node_uuid: NodeID = Field(
        ...,
        description="The node to get the port output from",
        alias="nodeUuid",
    )
    output: str = Field(
        ...,
        description="The port key in the node given by nodeUuid",
        regex=PROPERTY_KEY_RE,
    )

    class Config:
        extra = Extra.forbid
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # minimal
                {
                    "nodeUuid": "da5068e0-8a8d-4fb9-9516-56e5ddaef15b",
                    "output": "out_2",
                }
            ],
        }


class DownloadLink(BaseModel):
    """I/O port type to hold a generic download link to a file (e.g. S3 pre-signed link, etc)"""

    download_link: AnyUrl = Field(..., alias="downloadLink")
    label: str | None = Field(default=None, description="Display name")

    class Config:
        extra = Extra.forbid
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # minimal
                {
                    "downloadLink": "https://fakeimg.pl/250x100/",
                }
            ],
        }


## CUSTOM STORAGE SERVICES -----------
class BaseFileLink(BaseModel):
    """Base class for I/O port types with links to storage services"""

    store: LocationID = Field(
        ...,
        description="The store identifier: 0 for simcore S3, 1 for datcore",
    )

    path: StorageFileID = Field(
        ...,
        description="The path to the file in the storage provider domain",
    )

    label: str | None = Field(
        default=None,
        description="The real file name",
    )

    e_tag: str | None = Field(
        default=None,
        description="Entity tag that uniquely represents the file. The method to generate the tag is not specified (black box).",
        alias="eTag",
    )

    @validator("store", pre=True)
    @classmethod
    def legacy_enforce_str_to_int(cls, v):
        # SEE example 'legacy: store as string'
        if isinstance(v, str):
            return int(v)
        return v


class SimCoreFileLink(BaseFileLink):
    """I/O port type to hold a link to a file in simcore S3 storage"""

    dataset: str | None = Field(
        default=None,
        deprecated=True
        # TODO: Remove with storage refactoring
    )

    @validator("store", always=True)
    @classmethod
    def check_discriminator(cls, v):
        """Used as discriminator to cast to this class"""
        if v != 0:
            msg = f"SimCore store identifier must be set to 0, got {v}"
            raise ValueError(msg)
        return 0

    @validator("label", always=True, pre=True)
    @classmethod
    def pre_fill_label_with_filename_ext(cls, v, values):
        if v is None and "path" in values:
            return Path(values["path"]).name
        return v

    class Config:
        extra = Extra.forbid
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "store": 0,
                    "path": "94453a6a-c8d4-52b3-a22d-ccbf81f8d636/0a3b2c56-dbcd-4871-b93b-d454b7883f9f/input.txt",
                    "eTag": "859fda0cb82fc4acb4686510a172d9a9-1",
                    "label": "input.txt",
                },
                # legacy: store as string (SEE incident https://git.speag.com/oSparc/e2e-testing/-/issues/1)
                {
                    "store": "0",
                    "path": "50339632-ee1d-11ec-a0c2-02420a0194e4/23b1522f-225f-5a4c-9158-c4c19a70d4a8/output.h5",
                    "eTag": "f7e4c7076761a42a871e978c8691c676",
                },
                # minimal
                {
                    "store": 0,
                    "path": "api/0a3b2c56-dbcd-4871-b93b-d454b7883f9f/input.txt",
                },
                # w/ store id as int
                {
                    "store": 0,
                    "path": "94453a6a-c8d4-52b3-a22d-ccbf81f8d636/d4442ca4-23fd-5b6b-ba6d-0b75f711c109/y_1D.txt",
                },
            ],
        }


class DatCoreFileLink(BaseFileLink):
    """I/O port type to hold a link to a file in DATCORE storage"""

    label: str = Field(
        ...,
        description="The real file name",
    )

    dataset: str = Field(
        ...,
        description="Unique identifier to access the dataset on datcore (REQUIRED for datcore)",
    )

    @validator("store", always=True)
    @classmethod
    def check_discriminator(cls, v):
        """Used as discriminator to cast to this class"""

        if v != 1:
            msg = f"DatCore store must be set to 1, got {v}"
            raise ValueError(msg)
        return 1

    class Config:
        extra = Extra.forbid
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    # minimal
                    "store": 1,
                    "dataset": "N:dataset:ea2325d8-46d7-4fbd-a644-30f6433070b4",
                    "path": "N:package:32df09ba-e8d6-46da-bd54-f696157de6ce",
                    "label": "initial_WTstates",
                },
                # with store id as str
                {
                    "store": 1,
                    "dataset": "N:dataset:ea2325d8-46d7-4fbd-a644-30f6433070b4",
                    "path": "N:package:32df09ba-e8d6-46da-bd54-f696157de6ce",
                    "label": "initial_WTstates",
                },
            ],
        }


# Bundles all model links to a file vs PortLink
LinkToFileTypes = SimCoreFileLink | DatCoreFileLink | DownloadLink
