from pydantic import PositiveInt
from pydantic.types import NonNegativeInt

UserID = PositiveInt
ClusterID = NonNegativeInt

# dynamic services
DYNAMIC_SIDECAR_SERVICE_PREFIX = "dy-sidecar"
DYNAMIC_PROXY_SERVICE_PREFIX = "dy-proxy"

DYNAMIC_SIDECAR_DOCKER_IMAGE_RE = r"(^(local|itisfoundation|((([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]):[0-9]+))/)?(dynamic-sidecar):([\w]+)"
REGEX_DY_SERVICE_SIDECAR = fr"^{DYNAMIC_SIDECAR_SERVICE_PREFIX}_[a-zA-Z0-9-_]*"
REGEX_DY_SERVICE_PROXY = fr"^{DYNAMIC_PROXY_SERVICE_PREFIX}_[a-zA-Z0-9-_]*"
