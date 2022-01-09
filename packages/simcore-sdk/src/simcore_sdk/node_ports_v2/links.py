from pathlib import Path
from typing import Union

from models_library.projects_nodes_io import UUID_REGEX, BaseFileLink, DownloadLink
from models_library.projects_nodes_io import PortLink as BasePortLink
from pydantic import AnyUrl, Extra, Field, StrictBool, StrictFloat, StrictInt, StrictStr


class PortLink(BasePortLink):
    node_uuid: str = Field(..., regex=UUID_REGEX, alias="nodeUuid")


class FileLink(BaseFileLink):
    """allow all kind of file links"""

    class Config:
        extra = Extra.allow


DataItemValue = Union[
    StrictBool, StrictInt, StrictFloat, StrictStr, DownloadLink, PortLink, FileLink
]

ItemConcreteValue = Union[int, float, bool, str, Path]
ItemValue = Union[int, float, bool, str, AnyUrl]

__all__ = ["FileLink", "DownloadLink", "PortLink", "DataItemValue", "ItemConcreteValue"]
