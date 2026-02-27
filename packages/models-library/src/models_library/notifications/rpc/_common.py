from pydantic import BaseModel, ConfigDict

from .. import ChannelType, TemplateName
from .channels._email import EmailEnvelope

type Envelope = EmailEnvelope


class TemplateRef(BaseModel):
    channel: ChannelType
    template_name: TemplateName

    model_config = ConfigDict(frozen=True)
