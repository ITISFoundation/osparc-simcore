import os
import uuid
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator, Optional, Tuple

from aiohttp import web
from pydantic import ValidationError

MEGABYTES = 1024 * 2014


# VIEWERS MAP -----------------------------------------------------------------------------
class MatchNotFoundError(Exception):
    def __init__(self, reason):
        super().__init__()
        self.reason = reason


@dataclass
class ViewerInfo:
    key: str
    version: str
    label: str
    # name of the connection port, since it is service-dependent
    input_port_key: str = "input_1"

    @property
    def footprint(self) -> str:
        return f"{self.key}:{self.version}"

    @property
    def title(self) -> str:
        """ human readable title """
        return f"{self.label.capitalize()} v{self.version}"


#
# TODO: For the moment, viewers-filetype association is hard-coded
# TODO: The environs are tmp to give more flexibility with updates
#
_SIM4LIFE_VIEWER = ViewerInfo(
    key="simcore/services/dynamic/sim4life",
    version=os.environ.get("WEBSERVER_VIEWER_SIM4LIFE_VERSION", "1.0.16"),
    label="Sim4Life",
)
_RAWGRAPHS_VIEWER = ViewerInfo(
    key="simcore/services/dynamic/raw-graphs",
    version=os.environ.get("WEBSERVER_VIEWER_RAWGRAPH_VERSION", "2.10.6"),
    label="2D plot - RAWGraphs",
)

_FILETYPE_TO_VIEWER = {"DICOM": _SIM4LIFE_VIEWER, "CSV": _RAWGRAPHS_VIEWER}


def iter_supported_filetypes() -> Iterator[Tuple[str, ViewerInfo]]:
    for file_type, view_info in _FILETYPE_TO_VIEWER.items():
        yield file_type, deepcopy(view_info)


def find_compatible_viewer(
    file_type: str, file_size: Optional[int] = None
) -> ViewerInfo:
    try:
        viewer = _FILETYPE_TO_VIEWER[file_type]
    except KeyError:
        raise MatchNotFoundError(f"No viewer available for file type '{file_type}''")

    # Assumes size of the file in bytes TODO: configurable?
    if file_size is not None and file_size > 50 * MEGABYTES:
        raise MatchNotFoundError(f"File size {file_size*1E-6} MB is over allowed limit")

    return viewer


# UTILITIES ---------------------------------------------------------------
BASE_UUID = uuid.UUID("ca2144da-eabb-4daf-a1df-a3682050e25f")


@lru_cache()
def compose_uuid_from(*values) -> str:
    composition = "/".join(map(str, values))
    new_uuid = uuid.uuid5(BASE_UUID, composition)
    return str(new_uuid)


class ValidationMixin:
    @classmethod
    def from_request(cls, request: web.Request):
        try:
            obj = cls(**dict(request.query))
        except ValidationError as err:
            raise web.HTTPBadRequest(
                content_type="application/json",
                body=err.json(),
                reason=f"Invalid parameters {err.json(indent=1)}",
            )
        else:
            return obj
