"""Registry for notification template context models.

This module provides lazy-loading of context models from template directories.
Each template can optionally define its context model in a context.py file.
"""

import importlib
import logging
from typing import TYPE_CHECKING, Final

import notifications_library

if TYPE_CHECKING:
    from models_library.notifications import ChannelType, TemplateName

    from .template_context import NotificationsTemplateContext

_logger = logging.getLogger(__name__)


_CONTEXT_CLASS_NAME: Final[str] = "Context"


def get_context_model(channel: "ChannelType", template_name: "TemplateName") -> type["NotificationsTemplateContext"]:
    """
    Get the context model for a specific template.

    Attempts to import a context module from the template directory.
    Falls back to the base NotificationsTemplateContext if no specific context is defined.

    Args:
        channel: The notification channel (e.g., ChannelType.email)
        template_name: The template name (e.g., account_approved)

    Returns:
        The context model class for the template, or NotificationsTemplateContext as fallback
    """
    from .template_context import NotificationsTemplateContext  # noqa: PLC0415

    # Try to import context module for this template
    # Expected location: notifications_library.templates.{channel}.{template_name}.context
    module_path = f"{notifications_library.__name__}.templates.{channel}.{template_name}.context"

    try:
        module = importlib.import_module(module_path)
        context_class = getattr(module, _CONTEXT_CLASS_NAME, None)

        if context_class and issubclass(context_class, NotificationsTemplateContext):
            _logger.debug(
                "Loaded context model for %s/%s from %s",
                channel,
                template_name,
                module_path,
            )
            return context_class

        _logger.warning(
            "Module %s exists but does not define a valid Context class",
            module_path,
        )
    except ImportError:
        _logger.debug(
            "No custom context found for %s/%s, using base NotificationsTemplateContext",
            channel,
            template_name,
        )
    except Exception:
        _logger.exception(
            "Error loading context model from %s, using base NotificationsTemplateContext",
            module_path,
        )

    return NotificationsTemplateContext
