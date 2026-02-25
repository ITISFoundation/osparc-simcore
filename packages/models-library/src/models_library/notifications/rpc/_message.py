from typing import Any

from pydantic import BaseModel, ConfigDict

from . import Envelope
from ._common import TemplateRef


class SendMessageFromTemplateRequest(BaseModel):
    ref: TemplateRef
    template_context: dict[str, Any]

    envelope: Envelope

    model_config = ConfigDict(frozen=True)
