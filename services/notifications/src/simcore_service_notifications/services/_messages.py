from dataclasses import dataclass

from ._templates import TemplatesService


@dataclass(frozen=True)
class MessagesService:
    templates_service: TemplatesService
