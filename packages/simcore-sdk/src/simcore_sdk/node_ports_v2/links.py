from pathlib import Path
from typing import Any, Union

from models_library.basic_regex import UUID_RE
from models_library.projects_nodes_io import BaseFileLink, DownloadLink
from models_library.projects_nodes_io import PortLink as BasePortLink
from pydantic import (
    AnyUrl,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)


class PortLink(BasePortLink):
    node_uuid: str = Field(..., pattern=UUID_RE, alias="nodeUuid")  # type: ignore[assignment] # This overrides the base class it is ugly but needs its own PR to fix it


class FileLink(BaseFileLink):
    """allow all kind of file links"""

    model_config = ConfigDict(
        extra="allow",
    )


# TODO: needs to be in sync with project_nodes.InputTypes and project_nodes.OutputTypes
DataItemValue = Union[
    StrictBool,
    StrictInt,
    StrictFloat,
    StrictStr,
    DownloadLink,
    PortLink,
    FileLink,
    list[Any],  # arrays
    dict[str, Any],  # object
]

#
# - the port's value is stored as Optional[DataItemValue]
#   - order of union is used to parse object upon construction
# - DataItemValue values are resolved into an ItemValue using Port.get_value()
# - ItemValue values are resolved into ItemConcreteValue using Port.get()
# - ItemConcreteValue are the types finally consumed by the actual service port
#
SchemaValidatedTypes = Union[
    StrictBool, StrictInt, StrictFloat, StrictStr, list[Any], dict[str, Any]
]
ItemValue = Union[SchemaValidatedTypes, AnyUrl]
ItemConcreteValue = Union[SchemaValidatedTypes, Path]
ItemConcreteValueTypes = (
    type[StrictBool]
    | type[StrictInt]
    | type[StrictFloat]
    | type[StrictStr]
    | type[list[Any]]
    | type[dict[str, Any]]
    | type[Path]
)


__all__: tuple[str, ...] = (
    "DataItemValue",
    "DownloadLink",
    "FileLink",
    "ItemConcreteValue",
    "SchemaValidatedTypes",
    "PortLink",
)
