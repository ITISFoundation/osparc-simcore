from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from models_library.notifications import ChannelType, TemplateName
from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema


class BaseTemplateContext(BaseModel):
    product: SkipJsonSchema[dict[str, Any]]


_TEMPLATE_CONTEXT_REGISTRY: dict[tuple[ChannelType, TemplateName], type[BaseTemplateContext]] = {}

_T = TypeVar("_T", bound=type[BaseTemplateContext])


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


def register_template_context(
    channel: ChannelType,
    template_name: TemplateName,
) -> Callable[[_T], _T]:
    """Decorator to register a template context model.

    Args:
        channel: The notification channel (e.g., ChannelType.email)
        template_name: The template name

    Returns:
        The decorator function

    Example:
        @register_template_context(ChannelType.email, "account_approved")
        class AccountApprovedTemplateContext(BaseTemplateContext):
            ...
    """

    def decorator(cls: _T) -> _T:
        key = (channel, template_name)
        if key in _TEMPLATE_CONTEXT_REGISTRY:
            msg = f"Template context model already registered for {channel}/{template_name}"
            raise ValueError(msg)
        _TEMPLATE_CONTEXT_REGISTRY[key] = cls
        return cls

    return decorator


def get_template_context_model(
    channel: ChannelType,
    template_name: TemplateName,
) -> type[BaseTemplateContext]:
    return _TEMPLATE_CONTEXT_REGISTRY.get((channel, template_name), BaseTemplateContext)
