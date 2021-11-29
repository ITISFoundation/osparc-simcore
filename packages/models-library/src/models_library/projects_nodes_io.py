"""
    Models used as I/O of Nodes
"""

from pathlib import Path
from typing import Optional, Union
from uuid import UUID

from pydantic import AnyUrl, BaseModel, Extra, Field, constr, validator

from .services import PROPERTY_KEY_RE

NodeID = UUID

# Pydantic does not support exporting a jsonschema with Dict keys being something else than a str
# this is a regex for having uuids of type: 8-4-4-4-12 digits
UUID_REGEX = (
    r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)
NodeIDStr = constr(regex=UUID_REGEX)


class PortLink(BaseModel):
    """I/O port type to reference to an output port of another node in the same project"""

    node_uuid: NodeID = Field(
        ...,
        description="The node to get the port output from",
        example=["da5068e0-8a8d-4fb9-9516-56e5ddaef15b"],
        alias="nodeUuid",
    )
    output: str = Field(
        ...,
        description="The port key in the node given by nodeUuid",
        regex=PROPERTY_KEY_RE,
        example=["out_2"],
    )

    class Config:
        extra = Extra.forbid


class DownloadLink(BaseModel):
    """I/O port type to hold a generic download link to a file (e.g. S3 pre-signed link, etc)"""

    download_link: AnyUrl = Field(..., alias="downloadLink")
    label: Optional[str]

    class Config:
        extra = Extra.forbid


class BaseFileLink(BaseModel):
    """Base class for I/O port types with links to storage services"""

    # TODO: constructor will always cast to str here. We should perhaps set is as str. Actually
    # if we want to do hash in inputs/outputs ... we should have a single type for identifiers
    # Recall lru_cache options regarding types!!
    store: Union[str, int] = Field(
        ...,
        description="The store identifier: '0' or 0 for simcore S3, '1' or 1 for datcore",
        examples=["0", 1],
    )

    path: str = Field(
        ...,
        regex=r"^.+$",
        description="The path to the file in the storage provider domain",
        examples=[
            "N:package:b05739ef-260c-4038-b47d-0240d04b0599",
            "94453a6a-c8d4-52b3-a22d-ccbf81f8d636/d4442ca4-23fd-5b6b-ba6d-0b75f711c109/y_1D.txt",
        ],
    )

    label: Optional[str] = Field(
        None,
        description="The real file name",
        examples=["MyFile.txt"],
    )

    e_tag: Optional[str] = Field(
        None,
        description="Entity tag that uniquely represents the file. The method to generate the tag is not specified (black box).",
        alias="eTag",
    )


class SimCoreFileLink(BaseFileLink):
    """I/O port type to hold a link to a file in simcore S3 storage"""

    dataset: Optional[str] = Field(
        None,
        deprecated=True
        # TODO: Remove with storage refactoring
    )

    @validator("store", always=True)
    @classmethod
    def check_discriminator(cls, v):
        """Used as discriminator to cast to this class"""
        if v != "0":
            raise ValueError(f"SimCore store identifier must be set to 0, got {v}")
        return "0"

    @validator("label", always=True, pre=True)
    @classmethod
    def pre_fill_label_with_filename_ext(cls, v, values):
        if v is None and "path" in values:
            return Path(values["path"]).name
        return v

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "example": {
                "store": "0",
                "path": "api/0a3b2c56-dbcd-4871-b93b-d454b7883f9f/input.txt",
                "eTag": "859fda0cb82fc4acb4686510a172d9a9-1",
                "label": "input.txt",
            },
            "examples": [
                # minimal
                {
                    "store": "0",
                    "path": "api/0a3b2c56-dbcd-4871-b93b-d454b7883f9f/input.txt",
                }
            ],
        }


class DatCoreFileLink(BaseFileLink):
    """I/O port type to hold a link to a file in DATCORE storage"""

    label: str = Field(
        ...,
        description="The real file name",
        examples=["MyFile.txt"],
    )

    dataset: str = Field(
        ...,
        description="Unique identifier to access the dataset on datcore (REQUIRED for datcore)",
        example=["N:dataset:f9f5ac51-33ea-4861-8e08-5b4faf655041"],
    )

    @validator("store", always=True)
    @classmethod
    def check_discriminator(cls, v):
        """Used as discriminator to cast to this class"""

        if v != "1":
            raise ValueError(f"DatCore store must be set to 1, got {v}")
        return "1"

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "example": {
                # minimal
                "store": 1,
                "dataset": "N:dataset:ea2325d8-46d7-4fbd-a644-30f6433070b4",
                "path": "N:package:32df09ba-e8d6-46da-bd54-f696157de6ce",
                "label": "initial_WTstates",
            },
        }
