from typing import Any

from models_library.errors_classes import OsparcErrorMixin


class DirectorRuntimeError(OsparcErrorMixin, RuntimeError):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)

    msg_template: str = "Director-v0 unexpected error"


class ConfigurationError(DirectorRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"
