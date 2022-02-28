from pathlib import Path
from typing import Any, Dict, List, Union

from models_library.projects_nodes_io import UUID_REGEX, BaseFileLink, DownloadLink
from models_library.projects_nodes_io import PortLink as BasePortLink
from pydantic import AnyUrl, Extra, Field, StrictBool, StrictFloat, StrictInt, StrictStr


class PortLink(BasePortLink):
    node_uuid: str = Field(..., regex=UUID_REGEX, alias="nodeUuid")


class FileLink(BaseFileLink):
    """allow all kind of file links"""

    class Config:
        extra = Extra.allow


# TODO: needs to be in sync with project_nodes.InputTypes and project_nodes.OutputTypes
DataItemValue = Union[
    StrictBool,
    StrictInt,
    StrictFloat,
    StrictStr,
    DownloadLink,
    PortLink,
    FileLink,
    List[Any],  # arrays
    Dict[str, Any],  # object
]

ItemConcreteValue = Union[int, float, bool, str, Path, List[Any], Dict[str, Any]]
ItemValue = Union[int, float, bool, str, AnyUrl, List[Any], Dict[str, Any]]

__all__ = ["FileLink", "DownloadLink", "PortLink", "DataItemValue", "ItemConcreteValue"]
