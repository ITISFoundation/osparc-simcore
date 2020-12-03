from pathlib import Path
from typing import Optional, Union

from pydantic import (
    AnyUrl,
    BaseModel,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)


class PortLink(BaseModel):
    node_uuid: str = Field(..., alias="nodeUuid")
    output: str


class DownloadLink(BaseModel):
    download_link: AnyUrl = Field(..., alias="downloadLink")
    label: Optional[str]


class FileLink(BaseModel):
    store: Union[str, int]
    path: str
    dataset: Optional[str]
    label: Optional[str]


DataItemValue = Union[
    StrictBool, StrictInt, StrictFloat, StrictStr, DownloadLink, PortLink, FileLink
]

ItemConcreteValue = Union[int, float, bool, str, Path]
