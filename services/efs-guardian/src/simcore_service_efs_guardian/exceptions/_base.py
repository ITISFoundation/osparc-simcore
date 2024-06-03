from typing import Any

from models_library.errors_classes import OsparcErrorMixin


class EfsGuardianBaseError(OsparcErrorMixin, Exception):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)
