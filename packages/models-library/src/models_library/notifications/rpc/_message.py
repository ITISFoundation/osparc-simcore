from typing import Any

from pydantic import BaseModel, ConfigDict

from ._common import Envelope, TemplateRef


class SendMessageFromTemplateRequest(BaseModel):
    ref: TemplateRef
    template_context: dict[str, Any]

    envelope: Envelope

    model_config = ConfigDict(frozen=True)
