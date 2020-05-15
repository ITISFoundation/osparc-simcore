"""Director service configuration
"""

import logging
import os
from typing import Dict, Optional

from servicelib.client_session import APP_CLIENT_SESSION_KEY

DEBUG_MODE: bool = os.environ.get("LOGLEVEL", False) in ["true", "True", True]

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.WARNING,
    format="%(levelname)s:%(name)s-%(lineno)d: %(message)s",
)

API_VERSION: str = "v0"
API_ROOT: str = "api"

DIRECTOR_REGISTRY_CACHING: bool = os.environ.get("DIRECTOR_REGISTRY_CACHING", True) in [
    "true",
    "True",
    True,
]
DIRECTOR_REGISTRY_CACHING_TTL: int = int(
    os.environ.get("DIRECTOR_REGISTRY_CACHING_TTL", 15 * 60)
)

# for passing self-signed certificate to spawned services
DIRECTOR_SELF_SIGNED_SSL_SECRET_ID: str = os.environ.get(
    "DIRECTOR_SELF_SIGNED_SSL_SECRET_ID", ""
)
DIRECTOR_SELF_SIGNED_SSL_SECRET_NAME: str = os.environ.get(
    "DIRECTOR_SELF_SIGNED_SSL_SECRET_NAME", ""
)
DIRECTOR_SELF_SIGNED_SSL_FILENAME: str = os.environ.get(
    "DIRECTOR_SELF_SIGNED_SSL_FILENAME", ""
)

TRAEFIK_SIMCORE_ZONE: str = os.environ.get(
    "TRAEFIK_SIMCORE_ZONE", "internal_simcore_stack"
)
APP_REGISTRY_CACHE_DATA_KEY: str = __name__ + "_registry_cache_data"

REGISTRY_AUTH: bool = os.environ.get("REGISTRY_AUTH", False) in ["true", "True", True]
REGISTRY_USER: str = os.environ.get("REGISTRY_USER", "")
REGISTRY_PW: str = os.environ.get("REGISTRY_PW", "")
REGISTRY_URL: str = os.environ.get("REGISTRY_URL", "")
REGISTRY_SSL: bool = os.environ.get("REGISTRY_SSL", True) in ["true", "True", True]

EXTRA_HOSTS_SUFFIX: str = os.environ.get("EXTRA_HOSTS_SUFFIX", "undefined")

# these are the envs passed to the dynamic services by default
SERVICES_DEFAULT_ENVS: Dict[str, str] = {
    "POSTGRES_ENDPOINT": os.environ.get(
        "POSTGRES_ENDPOINT", "undefined postgres endpoint"
    ),
    "POSTGRES_USER": os.environ.get("POSTGRES_USER", "undefined postgres user"),
    "POSTGRES_PASSWORD": os.environ.get(
        "POSTGRES_PASSWORD", "undefined postgres password"
    ),
    "POSTGRES_DB": os.environ.get("POSTGRES_DB", "undefined postgres db"),
    "STORAGE_ENDPOINT": os.environ.get(
        "STORAGE_ENDPOINT", "undefined storage endpoint"
    ),
}

# some services need to know the published host to be functional (paraview)
# TODO: please review if needed
PUBLISHED_HOST_NAME: str = os.environ.get("PUBLISHED_HOST_NAME", "")

SWARM_STACK_NAME: str = os.environ.get("SWARM_STACK_NAME")

# used when in devel mode vs release mode
NODE_SCHEMA_LOCATION: str = os.environ.get(
    "NODE_SCHEMA_LOCATION", f"{API_ROOT}/{API_VERSION}/schemas/node-meta-v0.0.1.json"
)
# used to find the right network name
SIMCORE_SERVICES_NETWORK_NAME: Optional[str] = os.environ.get(
    "SIMCORE_SERVICES_NETWORK_NAME"
)
# useful when developing with an alternative registry namespace
SIMCORE_SERVICES_PREFIX: str = os.environ.get(
    "SIMCORE_SERVICES_PREFIX", "simcore/services"
)

# tracing
TRACING_ENABLED: bool = os.environ.get("TRACING_ENABLED", True) in [
    "true",
    "True",
    True,
]
TRACING_ZIPKIN_ENDPOINT: str = os.environ.get(
    "TRACING_ZIPKIN_ENDPOINT", "http://jaeger:9411"
)

__all__ = ["APP_CLIENT_SESSION_KEY"]
