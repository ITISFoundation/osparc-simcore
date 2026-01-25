from dataclasses import dataclass
from typing import ClassVar

from models_library.notifications import ChannelType


@dataclass(frozen=True)
class NotificationMessage[C]:
    channel: ClassVar[ChannelType]
    content: C
