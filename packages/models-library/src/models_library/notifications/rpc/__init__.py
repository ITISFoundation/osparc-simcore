from typing import Final

from pydantic import TypeAdapter

from ...rabbitmq_basic_types import RPCNamespace
from .._notifications import TemplateRef
from ._message import (
    SendMessageFromTemplateRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from ._template import (
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    SearchTemplatesResponse,
)

NOTIFICATIONS_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(RPCNamespace).validate_python("notifications")

__all__: tuple[str, ...] = (
    "PreviewTemplateRequest",
    "PreviewTemplateResponse",
    "SearchTemplatesResponse",
    "SendMessageFromTemplateRequest",
    "SendMessageRequest",
    "SendMessageResponse",
    "TemplateRef",
)
