import re
from types import MappingProxyType
from typing import Final

from models_library.services_enums import ServiceType

PROPERTY_TYPE_RE = r"^(number|integer|boolean|string|ref_contentSchema|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$"
PROPERTY_TYPE_TO_PYTHON_TYPE_MAP = {
    "integer": int,
    "number": float,
    "boolean": bool,
    "string": str,
}

FILENAME_RE = r".+"


# Add key prefixes for dynamic and computational services
DYNAMIC_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/dynamic"
COMPUTATIONAL_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/comp"
FRONTEND_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/frontend"


SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    rf"^(?P<key_prefix>{COMPUTATIONAL_SERVICE_KEY_PREFIX}|{DYNAMIC_SERVICE_KEY_PREFIX}|{FRONTEND_SERVICE_KEY_PREFIX})"
    r"/(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
SERVICE_ENCODED_KEY_RE: Final[re.Pattern[str]] = re.compile(
    rf"^(?P<key_prefix>{COMPUTATIONAL_SERVICE_KEY_PREFIX.replace('/', '%2F')}|{DYNAMIC_SERVICE_KEY_PREFIX.replace('/', '%2F')}|{FRONTEND_SERVICE_KEY_PREFIX.replace('/', '%2F')})"
    r"(?P<subdir>(%2F[a-z0-9][a-z0-9_.-]*)*%2F)?"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)


DYNAMIC_SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    rf"^{DYNAMIC_SERVICE_KEY_PREFIX}/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
DYNAMIC_SERVICE_KEY_FORMAT: Final[str] = (
    f"{DYNAMIC_SERVICE_KEY_PREFIX}/{{service_name}}"
)


COMPUTATIONAL_SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    rf"^{COMPUTATIONAL_SERVICE_KEY_PREFIX}/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
COMPUTATIONAL_SERVICE_KEY_FORMAT: Final[str] = (
    f"{COMPUTATIONAL_SERVICE_KEY_PREFIX}/{{service_name}}"
)


FRONTEND_SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    rf"^{FRONTEND_SERVICE_KEY_PREFIX}/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
FRONTEND_SERVICE_KEY_FORMAT: Final[str] = (
    f"{FRONTEND_SERVICE_KEY_PREFIX}/{{service_name}}"
)


SERVICE_TYPE_PREFIXES = MappingProxyType(
    {
        ServiceType.COMPUTATIONAL: COMPUTATIONAL_SERVICE_KEY_PREFIX,
        ServiceType.DYNAMIC: DYNAMIC_SERVICE_KEY_PREFIX,
        ServiceType.FRONTEND: FRONTEND_SERVICE_KEY_PREFIX,
    }
)

assert all(  # nosec
    not prefix.endswith("/") for prefix in SERVICE_TYPE_PREFIXES.values()
), "Service type prefixes must not end with '/'"
