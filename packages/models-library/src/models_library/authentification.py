from enum import auto

from .utils.enums import StrAutoEnum


class TwoFAAuthentificationMethod(StrAutoEnum):
    sms = auto()
    email = auto()
    disabled = auto()
