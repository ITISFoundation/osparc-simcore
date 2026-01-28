"""Registry for notification template context models.

This module provides lazy-loading of context models from template directories.
Each template can optionally define its context model in a context.py file.
"""

import importlib
import logging
from typing import Final, cast

from models_library.notifications import ChannelType, TemplateName

import notifications_library

from .template_context import BaseTemplateContext

_logger = logging.getLogger(__name__)


_CONTEXT_CLASS_NAME: Final[str] = "TemplateContext"


def get_context_model(channel: ChannelType, template_name: TemplateName) -> type[BaseTemplateContext]:
    """
    Get the context model for a specific template.

    Attempts to import a context module from the template directory.
    Falls back to the base BaseTemplateContext if no specific context is defined.

    Args:
        channel: The notification channel (e.g., ChannelType.email)
        template_name: The template name (e.g., account_approved)

    Returns:
        The context model class for the template, or BaseTemplateContext as fallback
    """
    # Try to import context module for this template
    # Expected location: notifications_library.templates.{channel}.{template_name}._context
    module_path = f"{notifications_library.__name__}.templates.{channel}.{template_name}._context"

    try:
        module = importlib.import_module(module_path)
        context_class = getattr(module, _CONTEXT_CLASS_NAME, None)

        if context_class and issubclass(context_class, BaseTemplateContext):
            _logger.debug(
                "Loaded context model for %s/%s from %s",
                channel,
                template_name,
                module_path,
            )
            return cast(type[BaseTemplateContext], context_class)

        _logger.warning(
            "Module %s exists but does not define a valid Context class",
            module_path,
        )
    except ImportError:
        _logger.debug(
            "No custom context found for %s/%s, using base BaseTemplateContext",
            channel,
            template_name,
        )
    except Exception:  # pylint: disable=W0718
        _logger.exception(
            "Error loading context model from %s, using base BaseTemplateContext",
            module_path,
        )

    return BaseTemplateContext
