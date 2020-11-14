from dataclasses import dataclass
import uuid
from aiohttp import web
from pydantic import ValidationError
from functools import lru_cache


MEGABYTES = 1E6
BASE_UUID = uuid.UUID("ca2144da-eabb-4daf-a1df-a3682050e25f")


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

    @property
    def footprint(self) -> str:
        return f"{self.key}:{self.version}"


SIM4LIFE_VIEWER = ViewerInfo("simcore/services/dynamic/sim4life", "1.0.16", "sim4life")


def find_compatible_viewer(file_size: int, file_type: str) -> ViewerInfo:
    # Assumes size of the file in bytes
    if file_size > 50*MEGABYTES:
        raise MatchNotFoundError("File limit surpassed")

    if file_type == "DICOM":
        return SIM4LIFE_VIEWER

    raise MatchNotFoundError("No")


# UTILITIES ---------------------------------------------------------------


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
            raise web.HTTPBadRequest(content_type="application/json", body=err.json())
        else:
            return obj
