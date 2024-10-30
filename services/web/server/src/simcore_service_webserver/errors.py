from typing import Any

from models_library.errors_classes import OsparcErrorMixin


class WebServerBaseError(OsparcErrorMixin, Exception):
    msg_template = "Unexpected error in web-server"

    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)
