from typing import Any, Final

# These are equivalent to pydantic export models but for responses
# SEE https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeldict
# SEE https://fastapi.tiangolo.com/tutorial/response-model/#use-the-response_model_exclude_unset-parameter
RESPONSE_MODEL_POLICY: Final[dict[str, Any]] = {
    "response_model_by_alias": True,
    "response_model_exclude_unset": True,
    "response_model_exclude_defaults": False,
    "response_model_exclude_none": False,
}

SECOND: Final[int] = 1
MINUTE: Final[int] = 60 * SECOND
DIRECTOR_CACHING_TTL: Final[int] = 15 * MINUTE
LIST_SERVICES_CACHING_TTL: Final[int] = 30 * SECOND
# default lease (in seconds) for the lock that coalesces concurrent cold-cache bulk fetches
# of the services manifest. It is the import-time default for the cache decorators and the
# default of the `CATALOG_DIRECTOR_BULK_FETCH_LEASE` setting that can override it at startup.
DEFAULT_DIRECTOR_BULK_FETCH_LEASE: Final[int] = 30 * SECOND

SIMCORE_SERVICE_SETTINGS_LABELS: Final[str] = "simcore.service.settings"
