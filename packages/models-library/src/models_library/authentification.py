from enum import auto

from .utils.enums import StrAutoEnum


class TwoFactorAuthentificationMethod(StrAutoEnum):
    SMS = auto()
    EMAIL = auto()
    DISABLED = auto()
