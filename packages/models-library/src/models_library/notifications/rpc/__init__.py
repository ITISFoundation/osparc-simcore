from typing import Final

from pydantic import TypeAdapter

from ...rabbitmq_basic_types import RPCNamespace
from ._message import (
    EmailContact,
    EmailEnvelope,
    SendMessageFromTemplateRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from ._template import (
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    SearchTemplatesResponse,
    TemplateRef,
)

NOTIFICATIONS_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(RPCNamespace).validate_python("notifications")

__all__: tuple[str, ...] = (
    "EmailContact",
    "EmailEnvelope",
    "PreviewTemplateRequest",
    "PreviewTemplateResponse",
    "SearchTemplatesResponse",
    "SendMessageFromTemplateRequest",
    "SendMessageRequest",
    "SendMessageResponse",
    "TemplateRef",
)
