from typing import Any

from fastapi import status

# SEE https://fastapi.tiangolo.com/advanced/additional-responses/#more-information-about-openapi-responses
JOB_OUTPUT_LOGFILE_RESPONSES: dict[int, dict[str, Any]] = {
    status.HTTP_200_OK: {
        "content": {
            "application/octet-stream": {
                "schema": {"type": "string", "format": "binary"}
            },
            "application/zip": {"schema": {"type": "string", "format": "binary"}},
            "text/plain": {"schema": {"type": "string"}},
        },
        "description": "Returns a log file",
    },
    status.HTTP_404_NOT_FOUND: {"description": "Log not found"},
}
