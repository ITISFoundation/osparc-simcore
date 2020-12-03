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

UUID_REGEX = (
    r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)
PROPERTY_KEY_RE = r"^[-_a-zA-Z0-9]+$"


class PortLink(BaseModel):
    node_uuid: str = Field(..., regex=UUID_REGEX, alias="nodeUuid")
    output: str = Field(..., regex=PROPERTY_KEY_RE)


class DownloadLink(BaseModel):
    download_link: AnyUrl = Field(..., alias="downloadLink")
    label: Optional[str]


class FileLink(BaseModel):
    store: Union[str, int]
    path: str = Field(..., regex=r".+")
    dataset: Optional[str]
    label: Optional[str]


DataItemValue = Union[
    StrictBool, StrictInt, StrictFloat, StrictStr, DownloadLink, PortLink, FileLink
]

ItemConcreteValue = Union[int, float, bool, str, Path]
