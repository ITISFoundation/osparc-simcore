from typing import Annotated, NamedTuple, TypeAlias

from fastapi.responses import StreamingResponse
from models_library.basic_regex import SIMPLE_VERSION_RE
from pydantic import StringConstraints

VersionStr: TypeAlias = Annotated[str, StringConstraints(strip_whitespace=True, pattern=SIMPLE_VERSION_RE)]  # noqa: UP040

FileNameStr: TypeAlias = Annotated[str, StringConstraints(strip_whitespace=True)]  # noqa: UP040


class LogStreamingResponse(StreamingResponse):
    media_type = "application/x-ndjson"


class SseStreamingResponse(StreamingResponse):
    media_type = "text/event-stream"


class NameValueTuple(NamedTuple):
    name: str
    value: str
