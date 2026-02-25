from dataclasses import dataclass

from ._templates_service import TemplatesService


@dataclass(frozen=True)
class MessagesService:
    templates_service: TemplatesService
