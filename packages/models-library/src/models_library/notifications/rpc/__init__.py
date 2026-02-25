from typing import Final

from pydantic import TypeAdapter

from ...rabbitmq_basic_types import RPCNamespace
from ._common import TemplateRef
from ._message import SendMessageFromTemplateRequest
from ._template import (
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    SearchTemplatesResponse,
)
from .channels._email import EmailEnvelope

NOTIFICATIONS_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(RPCNamespace).validate_python("notifications")


type Envelope = EmailEnvelope


__all__: tuple[str, ...] = (
    "PreviewTemplateRequest",
    "PreviewTemplateResponse",
    "SearchTemplatesResponse",
    "SendMessageFromTemplateRequest",
    "TemplateRef",
)
