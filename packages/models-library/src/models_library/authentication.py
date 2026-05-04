from enum import auto

from .utils.enums import StrAutoEnum


class TwoFactorAuthenticationMethod(StrAutoEnum):
    SMS = auto()
    EMAIL = auto()
    DISABLED = auto()
