from typing import Any, Final

from fastapi import status
from simcore_service_api_server.models.basic_types import HTTPExceptionModel

from ...core.settings import BasicSettings

API_SERVER_DEV_FEATURES_ENABLED: Final[
    bool
] = BasicSettings.create_from_envs().API_SERVER_DEV_FEATURES_ENABLED

NOT_IMPLEMENTED_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_501_NOT_IMPLEMENTED: {
        "description": "Not implemented",
        "model": HTTPExceptionModel,
    }
}
