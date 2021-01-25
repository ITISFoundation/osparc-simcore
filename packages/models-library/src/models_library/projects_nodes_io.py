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
NodeID_AsDictKey = constr(regex=UUID_REGEX)


class PortLink(BaseModel):
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
    download_link: AnyUrl = Field(..., alias="downloadLink")
    label: Optional[str]

    class Config:
        extra = Extra.forbid


class BaseFileLink(BaseModel):
    store: Union[str, int] = Field(
        ...,
        description="The store identifier, '0' or 0 for simcore S3, '1' or 1 for datcore",
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
    e_tag: Optional[str] = Field(
        None,
        description="Entity tag that uniquely represents the file. The method to generate the tag is not specified (black box).",
        alias="eTag",
    )
    label: Optional[str] = Field(
        None,
        description="The real file name",
        examples=["MyFile.txt"],
    )

    class Config:
        extra = Extra.forbid


class SimCoreFileLink(BaseFileLink):
    @validator("label", always=True, pre=True)
    @classmethod
    def pre_fill_label_with_filename_ext(cls, v, values):
        if v is None and "path" in values:
            return Path(values["path"]).name

        return v

    class Config:
        extra = Extra.forbid


class DatCoreFileLink(BaseFileLink):
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

    class Config:
        extra = Extra.forbid
