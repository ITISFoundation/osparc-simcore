from pydantic import PositiveInt
from pydantic.types import NonNegativeInt

UserID = PositiveInt
ClusterID = NonNegativeInt

# dynamic services
DYNAMIC_SIDECAR_SERVICE_PREFIX = "dy-sidecar"
DYNAMIC_PROXY_SERVICE_PREFIX = "dy-proxy"

# label storing scheduler_data updated
# at the end of an observation cycle
DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL = "io.osparc.scheduler-data"

DYNAMIC_SIDECAR_DOCKER_IMAGE_RE = (
    r"(^(local|itisfoundation)/)?(dynamic-sidecar):([\w]+)"
)
REGEX_DY_SERVICE_SIDECAR = fr"^{DYNAMIC_SIDECAR_SERVICE_PREFIX}_[a-zA-Z0-9-_]*"
REGEX_DY_SERVICE_PROXY = fr"^{DYNAMIC_PROXY_SERVICE_PREFIX}_[a-zA-Z0-9-_]*"
