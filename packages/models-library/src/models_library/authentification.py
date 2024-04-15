from enum import auto

from .utils.enums import StrAutoEnum


class TwoFAAuthentificationMethod(StrAutoEnum):
    SMS = auto()
    EMAIL = auto()
    DISABLED = auto()
