from typing import Any

from models_library.errors_classes import OsparcErrorMixin


class AgentRuntimeError(OsparcErrorMixin, RuntimeError):
    def __init__(self, **ctx: Any) -> None:
        super().__init__(**ctx)

    msg_template: str = "Agent unexpected error"


class NoServiceVolumesFoundError(AgentRuntimeError):
    msg_template: str = (
        "Could not detect any unused volumes after waiting '{period}' seconds for "
        "volumes to be released after closing all container for service='{node_id}'"
    )
