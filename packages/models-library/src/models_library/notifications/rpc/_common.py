from pydantic import BaseModel, ConfigDict

from .. import ChannelType, TemplateName


class TemplateRef(BaseModel):
    channel: ChannelType
    template_name: TemplateName

    model_config = ConfigDict(frozen=True)
