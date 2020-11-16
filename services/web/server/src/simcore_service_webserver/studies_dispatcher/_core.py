import uuid
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache

from aiohttp import web
from pydantic import ValidationError
from typing import Iterator, Tuple

MEGABYTES = 1e6


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
    input_port_key: str = "input_1" # name of the connection port

    @property
    def footprint(self) -> str:
        return f"{self.key}:{self.version}"

    @property
    def title(self) -> str:
        """ human readable title """
        return f"{self.label.capitalize} v{self.version}"


#
# NOTE: For the moment, viewers-filetype association is hard-coded
#
_SIM4LIFE_VIEWER = ViewerInfo(key="simcore/services/dynamic/sim4life", version="1.0.16", label="sim4life")
_FILETYPE_TO_VIEWER = {"DICOM": _SIM4LIFE_VIEWER}


def iter_supported_filetypes() -> Iterator[Tuple[str, ViewerInfo]]:
    for file_type, view_info in _FILETYPE_TO_VIEWER.items():
        yield file_type, deepcopy(view_info)


def find_compatible_viewer(file_size: int, file_type: str) -> ViewerInfo:
    # Assumes size of the file in bytes
    if file_size > 50 * MEGABYTES:
        raise MatchNotFoundError("File limit surpassed")

    try:
        viewer = _FILETYPE_TO_VIEWER[file_type]
    except KeyError:
        raise MatchNotFoundError("No")

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
    def create_from(cls, request: web.Request):
        try:
            obj = cls(**request.query.keys())
        except ValidationError as err:
            raise web.HTTPBadRequest(
                content_type="application/json",
                body=err.json(),
                reason=f"Invalid parameters {err.json(indent=1)}",
            )
        else:
            return obj
