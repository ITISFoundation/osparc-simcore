from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

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

#
# - the port's value is stored as Optional[DataItemValue]
#   - order of union is used to parse object upon construction
# - DataItemValue values are resolved into an ItemValue using Port.get_value()
# - ItemValue values are resolved into ItemConcreteValue using Port.get()
# - ItemConcreteValue are the types finally consumed by the actual service port
#
BasicValueTypes = Union[int, float, bool, str, List[Any], Dict[str, Any]]
ItemValue = Union[BasicValueTypes, AnyUrl]
ItemConcreteValue = Union[BasicValueTypes, Path]


__all__: Tuple[str, ...] = (
    "DataItemValue",
    "DownloadLink",
    "FileLink",
    "ItemConcreteValue",
    "PortLink",
)
