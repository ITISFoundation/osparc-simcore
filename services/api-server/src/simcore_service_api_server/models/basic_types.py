import re

from common_library.pydantic_basic_types import ConstrainedStr
from fastapi.responses import StreamingResponse
from models_library.basic_regex import SIMPLE_VERSION_RE


class VersionStr(ConstrainedStr):
    strip_whitespace = True
    regex = re.compile(SIMPLE_VERSION_RE)


class FileNameStr(ConstrainedStr):
    strip_whitespace = True


class LogStreamingResponse(StreamingResponse):
    media_type = "application/x-ndjson"
