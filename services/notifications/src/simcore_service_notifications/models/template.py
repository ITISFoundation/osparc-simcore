from abc import ABC
from dataclasses import dataclass
from typing import Any

from models_library.notifications import ChannelType, TemplateName
from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema


class BaseTemplateContext(BaseModel):
    product: SkipJsonSchema[dict[str, Any]]


@dataclass(frozen=True)
class TemplateRef:
    """
    Uniquely identifies a template in the system.
    """

    channel: ChannelType
    template_name: TemplateName


@dataclass(frozen=True)
class Template(ABC):
    ref: TemplateRef
    context_model: type[BaseTemplateContext]

    parts: tuple[str, ...]
