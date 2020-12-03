from pathlib import Path
from typing import Union

from models_library.projects_nodes_io import BaseFileLink, DownloadLink, PortLink
from pydantic import Extra, StrictBool, StrictFloat, StrictInt, StrictStr


class FileLink(BaseFileLink):
    """ allow all kind of file links """

    class Config:
        extra = Extra.allow


DataItemValue = Union[
    StrictBool, StrictInt, StrictFloat, StrictStr, DownloadLink, PortLink, FileLink
]

ItemConcreteValue = Union[int, float, bool, str, Path]

__all__ = ["FileLink", "DownloadLink", "PortLink", "DataItemValue", "ItemConcreteValue"]
