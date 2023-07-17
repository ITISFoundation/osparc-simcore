from typing import Any, Final

from fastapi import status

from ...core.settings import BasicSettings

job_output_logfile_responses: dict[int | str, dict[str, Any]] = {
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


API_SERVER_DEV_FEATURES_ENABLED: Final[
    bool
] = BasicSettings.create_from_envs().API_SERVER_DEV_FEATURES_ENABLED
