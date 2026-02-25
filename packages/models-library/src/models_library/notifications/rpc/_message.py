from typing import Any

from pydantic import BaseModel, ConfigDict

from ._types import Envelope, TemplateRef


class SendMessageFromTemplateRequest(BaseModel):
    ref: TemplateRef
    context: dict[str, Any]

    envelope: Envelope

    model_config = ConfigDict(frozen=True)
