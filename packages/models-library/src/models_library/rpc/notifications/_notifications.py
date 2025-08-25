from typing import Annotated

from pydantic import BaseModel, Field

from .channels import Channel
from .events import Event


class Notification(BaseModel):
    event: Annotated[Event, Field(discriminator="type")]
    channel: Annotated[Channel, Field(discriminator="type")]
