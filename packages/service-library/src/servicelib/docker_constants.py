from typing import Final

PREFIX_DYNAMIC_SIDECAR_VOLUMES: Final[str] = "dyv"

SUFFIX_EGRESS_PROXY_NAME: Final[str] = "egress"

# NOTE: since a user inside the docker-compose spec can define
# their own networks, this name tries to be as unique as possible
# NOTE: length is 11 character. When running
# `docker compose up`, the network will result in having a 53
# character prefix in front. Max allowed network name is 64.
DEFAULT_USER_SERVICES_NETWORK_NAME: Final[str] = "back----end"
