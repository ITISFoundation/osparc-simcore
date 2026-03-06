from typing import Final

from pydantic import TypeAdapter

from ...rabbitmq_basic_types import RPCNamespace
from ._template import (
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    SearchTemplatesResponse,
    TemplateRef,
)

NOTIFICATIONS_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(RPCNamespace).validate_python("notifications")

__all__: tuple[str, ...] = (
    "PreviewTemplateRequest",
    "PreviewTemplateResponse",
    "SearchTemplatesResponse",
    "TemplateRef",
)
