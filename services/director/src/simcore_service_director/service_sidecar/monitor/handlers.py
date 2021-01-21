from .handlers_base import BaseEventHandler
from typing import Set

# register all handlers defined in this module here
REGISTERED_HANDLERS: Set[BaseEventHandler] = set()