from typing import Any

from models_library.errors_classes import OsparcErrorMixin


class AgentRuntimeError(OsparcErrorMixin, RuntimeError):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)

    msg_template: str = "Agent unexpected error"


class NoServiceVolumesFoundError(AgentRuntimeError):
    msg_template: str = "Could not find any unused volumes for service {node_id}"
