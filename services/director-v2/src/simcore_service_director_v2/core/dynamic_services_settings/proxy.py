import random

from models_library.basic_types import PortInt
from pydantic import Field
from settings_library.base import BaseCustomSettings


class DynamicSidecarProxySettings(BaseCustomSettings):
    DYNAMIC_SIDECAR_CADDY_VERSION: str = Field(
        "2.6.4-alpine",
        description="current version of the Caddy image to be pulled and used from dockerhub",
    )
    DYNAMIC_SIDECAR_CADDY_ADMIN_API_PORT: PortInt = Field(
        default_factory=lambda: random.randint(1025, 65535),  # noqa: S311
        description="port where to expose the proxy's admin API",
    )

    PROXY_EXPOSE_PORT: bool = Field(
        default=False,
        description="exposes the proxy on localhost for debugging and testing",
    )
