from typing import Final

from pydantic import TypeAdapter

from ...rabbitmq_basic_types import RPCNamespace
from ._email import (
    Addressing,
    EmailAddressing,
    EmailAttachment,
    EmailContact,
    EmailContent,
    EmailMessage,
    Message,
)
from ._message import (
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
    "Addressing",
    "EmailAddressing",
    "EmailAttachment",
    "EmailContact",
    "EmailContent",
    "EmailMessage",
    "Message",
    "PreviewTemplateRequest",
    "PreviewTemplateResponse",
    "SearchTemplatesResponse",
    "SendMessageFromTemplateRequest",
    "SendMessageRequest",
    "SendMessageResponse",
    "TemplateRef",
)
