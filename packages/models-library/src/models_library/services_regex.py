import re
from types import MappingProxyType
from typing import Final

from .services_enums import ServiceType

PROPERTY_TYPE_RE = r"^(number|integer|boolean|string|ref_contentSchema|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$"
PROPERTY_TYPE_TO_PYTHON_TYPE_MAP = {
    "integer": int,
    "number": float,
    "boolean": bool,
    "string": str,
}

FILENAME_RE = r".+"


SERVICE_TYPE_TO_NAME_MAP = MappingProxyType(
    {
        ServiceType.COMPUTATIONAL: "comp",
        ServiceType.DYNAMIC: "dynamic",
        ServiceType.FRONTEND: "frontend",
    }
)

# e.g. simcore/services/comp/opencor
SERVICE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^simcore/services/"
    rf"(?P<type>({ '|'.join(SERVICE_TYPE_TO_NAME_MAP.values()) }))/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)

# e.g. simcore%2Fservices%2Fcomp%2Fopencor
SERVICE_ENCODED_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^simcore%2Fservices%2F"
    rf"(?P<type>({'|'.join(SERVICE_TYPE_TO_NAME_MAP.values())}))%2F"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*%2F)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
)


def create_key_prefix(service_type: ServiceType) -> str:
    return f"simcore/services/{SERVICE_TYPE_TO_NAME_MAP[service_type]}"


COMPUTATIONAL_SERVICE_KEY_PREFIX: Final[str] = create_key_prefix(
    ServiceType.COMPUTATIONAL
)
DYNAMIC_SERVICE_KEY_PREFIX: Final[str] = create_key_prefix(ServiceType.DYNAMIC)
FRONTEND_SERVICE_KEY_PREFIX: Final[str] = create_key_prefix(ServiceType.FRONTEND)


def create_key_regex(service_type: ServiceType) -> re.Pattern[str]:
    return re.compile(
        rf"^simcore/services/{SERVICE_TYPE_TO_NAME_MAP[service_type]}/"
        r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
        r"(?P<name>[a-z0-9-_]+[a-z0-9])$"
    )


def create_key_format(service_type: ServiceType) -> str:
    return f"simcore/services/{SERVICE_TYPE_TO_NAME_MAP[service_type]}/{{service_name}}"


COMPUTATIONAL_SERVICE_KEY_RE: Final[re.Pattern[str]] = create_key_regex(
    ServiceType.COMPUTATIONAL
)
COMPUTATIONAL_SERVICE_KEY_FORMAT: Final[str] = create_key_format(
    ServiceType.COMPUTATIONAL
)

DYNAMIC_SERVICE_KEY_RE: Final[re.Pattern[str]] = create_key_regex(ServiceType.DYNAMIC)
DYNAMIC_SERVICE_KEY_FORMAT: Final[str] = create_key_format(ServiceType.DYNAMIC)

FRONTEND_SERVICE_KEY_RE: Final[re.Pattern[str]] = create_key_regex(ServiceType.FRONTEND)
FRONTEND_SERVICE_KEY_FORMAT: Final[str] = create_key_format(ServiceType.FRONTEND)


SERVICE_TYPE_TO_PREFIX_MAP = MappingProxyType(
    {
        ServiceType.COMPUTATIONAL: COMPUTATIONAL_SERVICE_KEY_PREFIX,
        ServiceType.DYNAMIC: DYNAMIC_SERVICE_KEY_PREFIX,
        ServiceType.FRONTEND: FRONTEND_SERVICE_KEY_PREFIX,
    }
)

assert all(  # nosec
    not prefix.endswith("/") for prefix in SERVICE_TYPE_TO_PREFIX_MAP.values()
), "Service type prefixes must not end with '/'"
