import re
from typing import Final

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

DYNAMIC_SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^simcore/services/dynamic/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
DYNAMIC_SERVICE_KEY_FORMAT = "simcore/services/dynamic/{service_name}"


# Computational regex & format
COMPUTATIONAL_SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^simcore/services/comp/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)
COMPUTATIONAL_SERVICE_KEY_FORMAT: Final[str] = "simcore/services/comp/{service_name}"
