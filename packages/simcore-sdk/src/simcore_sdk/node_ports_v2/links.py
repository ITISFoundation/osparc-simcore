from pathlib import Path
from typing import Any, TypeAlias

from models_library.projects_nodes_io import BaseFileLink, DownloadLink, PortLink
from pydantic import AnyUrl, Extra, StrictBool, StrictFloat, StrictInt, StrictStr


class FileLink(BaseFileLink):
    """allow all kind of file links"""

    class Config:
        extra = Extra.allow


# TODO: needs to be in sync with project_nodes.InputTypes and project_nodes.OutputTypes
DataItemValue: TypeAlias = (
    StrictBool
    | StrictInt
    | StrictFloat
    | StrictStr
    | DownloadLink
    | PortLink
    | FileLink
    | list[Any]  # arrays
    | dict[str, Any]  # object
)

#
# - the port's value is stored as Optional[DataItemValue]
#   - order of union is used to parse object upon construction
# - DataItemValue values are resolved into an ItemValue using Port.get_value()
# - ItemValue values are resolved into ItemConcreteValue using Port.get()
# - ItemConcreteValue are the types finally consumed by the actual service port
#
SchemaValidatedTypes: TypeAlias = (
    StrictBool | StrictInt | StrictFloat | StrictStr | list[Any] | dict[str, Any]
)

ItemValue: TypeAlias = SchemaValidatedTypes | AnyUrl
ItemConcreteValue: TypeAlias = SchemaValidatedTypes | Path
ItemConcreteValueTypes: TypeAlias = (
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
