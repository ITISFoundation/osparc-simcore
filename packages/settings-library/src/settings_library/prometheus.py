from functools import cached_property

from pydantic import AnyUrl, SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import MixinServiceSettings

from .basic_types import VersionTag


class PrometheusSettings(BaseCustomSettings, MixinServiceSettings):
    PROMETHEUS_URL: AnyUrl
    PROMETHEUS_VTAG: VersionTag = "v1"
    PROMETHEUS_USERNAME: str | None = None
    PROMETHEUS_PASSWORD: SecretStr | None = None

    @cached_property
    def base_url(self) -> str:
        return f"{self.PROMETHEUS_URL}/api/{self.PROMETHEUS_VTAG}/query"

    @cached_property
    def origin(self) -> str:
        return self._build_origin_url(prefix="PROMETHEUS")

    @cached_property
    def api_url(self) -> str:
        assert self.PROMETHEUS_URL.host  # nosec
        prometheus_url: str = str(
            AnyUrl.build(
                scheme=self.PROMETHEUS_URL.scheme,
                username=self.PROMETHEUS_USERNAME,
                password=self.PROMETHEUS_PASSWORD.get_secret_value()
                if self.PROMETHEUS_PASSWORD
                else None,
                host=self.PROMETHEUS_URL.host,
                port=self.PROMETHEUS_URL.port,
                path=self.PROMETHEUS_URL.path,
            )
        )
        return prometheus_url
