import re
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


# e.g. simcore/services/comp/opencor
SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^simcore/services/"
    r"(?P<type>(comp|dynamic|frontend))/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
# e.g. simcore%2Fservices%2Fcomp%2Fopencor
SERVICE_ENCODED_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^simcore%2Fservices%2F"
    r"(?P<type>(comp|dynamic|frontend))%2F"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*%2F)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)

# Add key prefixes for dynamic and computational services
DYNAMIC_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/dynamic"
DYNAMIC_SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    rf"^{DYNAMIC_SERVICE_KEY_PREFIX}/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)

COMPUTATIONAL_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/comp"
COMPUTATIONAL_SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    rf"^{COMPUTATIONAL_SERVICE_KEY_PREFIX}/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)

FRONTEND_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/frontend"

FRONTEND_SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    rf"^{FRONTEND_SERVICE_KEY_PREFIX}/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)

# Add service type prefixes mapping (moved from _services_sql.py)
SERVICE_TYPE_PREFIXES = {
    ServiceType.COMPUTATIONAL: COMPUTATIONAL_SERVICE_KEY_PREFIX,
    ServiceType.DYNAMIC: DYNAMIC_SERVICE_KEY_PREFIX,
    ServiceType.FRONTEND: FRONTEND_SERVICE_KEY_PREFIX,
}
