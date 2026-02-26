from enum import auto

from models_library.utils.enums import StrAutoEnum


class ServiceCategory(StrAutoEnum):
    LEGACY = auto()
    DY_PROXY = auto()
    DY_SIDECAR = auto()


type ServiceName = str
