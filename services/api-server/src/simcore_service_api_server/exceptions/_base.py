from typing import Any

from models_library.errors_classes import OsparcErrorMixin


class ApiServerBaseError(OsparcErrorMixin, Exception):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)
