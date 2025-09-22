from typing import Annotated

from pydantic import BaseModel, Field


class StreamHeaders(BaseModel):
    last_event_id: Annotated[
        str | None,
        Field(
            description="Optional last event ID",
            alias="Last-Event-ID",
        ),
    ] = None
