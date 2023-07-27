from typing import Final

# These are equivalent to pydantic export models but for responses
# SEE https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeldict
# SEE https://fastapi.tiangolo.com/tutorial/response-model/#use-the-response_model_exclude_unset-parameter
RESPONSE_MODEL_POLICY: Final[dict[str, bool]] = {
    "response_model_by_alias": True,
    "response_model_exclude_unset": True,
    "response_model_exclude_defaults": False,
    "response_model_exclude_none": False,
}

SECOND: Final[int] = 1
MINUTE: Final[int] = 60 * SECOND
DIRECTOR_CACHING_TTL: Final[int] = 5 * MINUTE
LIST_SERVICES_CACHING_TTL: Final[int] = 30 * SECOND

SIMCORE_SERVICE_SETTINGS_LABELS: Final[str] = "simcore.service.settings"
