from fastapi import Header
from pydantic.types import PositiveInt

#
# Based on discussion https://github.com/tiangolo/fastapi/issues/362#issuecomment-584104025
#
# TODO: add heuristics with max file size to config Timeout?
# SEE api/routes/files.py::upload_file
#

GB = 1024 * 1024 * 1024
MAX_UPLOAD_SIZE = 1 * GB  # TODO: settings?


async def valid_content_length(
    content_length: PositiveInt = Header(..., lt=MAX_UPLOAD_SIZE)
):
    # TODO: use this to replace   content_length: Optional[str] = Header(None),
    return content_length
