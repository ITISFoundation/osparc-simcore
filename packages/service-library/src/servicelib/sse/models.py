from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


class SSEHeaders(BaseModel):
    last_event_id: Annotated[
        str | None,
        Field(
            description="Optional last event ID",
            alias="Last-Event-ID",
        ),
    ] = None


def _normalize_data(v: str | list[str]) -> list[str]:
    if isinstance(v, str):
        lines = v.splitlines()
        return lines if lines else [""]
    return v


class SSEEvent(BaseModel):
    id: str | None = None
    event: str | None = None
    data: Annotated[str | list[str], BeforeValidator(_normalize_data)]
    retry: int | None = None

    def serialize(self) -> bytes:
        lines = []
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.event is not None:
            lines.append(f"event: {self.event}")
        lines.extend(f"data: {line}" for line in self.data)
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")

        payload = "\n".join(lines) + "\n\n"
        return payload.encode("utf-8")
