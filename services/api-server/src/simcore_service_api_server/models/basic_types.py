from typing import Annotated, TypeAlias

from fastapi.responses import StreamingResponse
from models_library.basic_regex import SIMPLE_VERSION_RE
from pydantic import StringConstraints

VersionStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=SIMPLE_VERSION_RE)
]

FileNameStr: TypeAlias = Annotated[str, StringConstraints(strip_whitespace=True)]


class LogStreamingResponse(StreamingResponse):
    media_type = "application/x-ndjson"
