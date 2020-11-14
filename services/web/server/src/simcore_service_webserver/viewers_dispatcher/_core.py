from dataclasses import dataclass
from typing import Optional
import uuid

from functools import lru_cache

BASE_UUID = uuid.UUID("ca2144da-eabb-4daf-a1df-a3682050e25f")


@dataclass
class ViewerInfo:
    key: str
    version: str
    label: str

    @property
    def footprint(self) -> str:
        return f"{self.key}:{self.version}"


SIM4LIFE_VIEWER = ViewerInfo("simcore/services/dynamic/sim4life", "1.0.16", "sim4life")



class MatchNotFoundError(Exception):
    def __init__(self, reason):
        super().__init__()
        self.reason = reason


def find_compatible_viewer(file_size: int, file_type: str) -> ViewerInfo:
    # FIXME: temporarily hard-coded
    # if file_size>MAXLIMIT:
    #    raise MatchNotFoundError("File limit surpassed")

    if file_type == "DICOM":
        return SIM4LIFE_VIEWER

    raise MatchNotFoundError("No")



@lru_cache()
def compose_uuid_from( *values ) -> str:
    composition = "/".join(map(str, values))
    new_uuid = uuid.uuid5(BASE_UUID, composition)
    return str(new_uuid)
