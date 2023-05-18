from functools import cached_property

from pydantic import AnyUrl, SecretStr, parse_obj_as
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import MixinServiceSettings

from .basic_types import VersionTag


class PrometheusSettings(BaseCustomSettings, MixinServiceSettings):
    PROMETHEUS_URL: AnyUrl = parse_obj_as(AnyUrl, "http://prometheus:9090")
    PROMETHEUS_VTAG: VersionTag = VersionTag("v1")
    PROMETHEUS_USERNAME: str | None = None
    PROMETHEUS_PASSWORD: SecretStr | None = None

    @cached_property
    def base_url(self) -> str:
        return f"{self.PROMETHEUS_URL}/api/{self.PROMETHEUS_VTAG}/query"

    @cached_property
    def origin(self) -> str:
        return self._build_origin_url(prefix="PROMETHEUS")
