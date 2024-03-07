from typing import Any

from models_library.errors_classes import OsparcErrorMixin


class NotifierError(OsparcErrorMixin, Exception):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)


class TemplatesNotFoundError(NotifierError):
    msg_template = "Could not find {templates}"


class UserNotFoundError(NotifierError):
    msg_template = "Cound not find user with id={user_id}"
