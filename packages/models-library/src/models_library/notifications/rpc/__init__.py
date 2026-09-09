from typing import Final

from pydantic import TypeAdapter

from ...rabbitmq_basic_types import RPCNamespace
from ._email import (
    EmailAddressing,
    EmailAttachment,
    EmailContact,
    EmailContent,
    EmailMessage,
    SenderIdentity,
)
from ._message import (
    SendMessageFromTemplateRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from ._sms import (
    PhoneNumberStr,
    SmsAddressing,
    SmsContact,
    SmsContent,
    SmsMessage,
)
from ._template import (
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    SearchTemplatesResponse,
    TemplateRef,
)
from ._types import Addressing, Message

NOTIFICATIONS_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(RPCNamespace).validate_python("notifications")

__all__: tuple[str, ...] = (
    "Addressing",
    "EmailAddressing",
    "EmailAttachment",
    "EmailContact",
    "EmailContent",
    "EmailMessage",
    "Message",
    "PhoneNumberStr",
    "PreviewTemplateRequest",
    "PreviewTemplateResponse",
    "SearchTemplatesResponse",
    "SendMessageFromTemplateRequest",
    "SendMessageRequest",
    "SendMessageResponse",
    "SenderIdentity",
    "SmsAddressing",
    "SmsContact",
    "SmsContent",
    "SmsMessage",
    "TemplateRef",
)
