import re

from fastapi.responses import StreamingResponse
from models_library.basic_regex import VERSION_RE
from pydantic import ConstrainedStr


class VersionStr(ConstrainedStr):
    strip_whitespace = True
    regex = re.compile(VERSION_RE)


class FileNameStr(ConstrainedStr):
    strip_whitespace = True


class LogStreamingResponse(StreamingResponse):
    media_type = "application/x-ndjson"
