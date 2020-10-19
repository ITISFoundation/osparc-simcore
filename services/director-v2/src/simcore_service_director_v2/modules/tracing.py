## packages/service-library/src/servicelib/tracing.py
from pydantic import AnyHttpUrl, BaseSettings

from ..core.settings import CommonConfig


# Module's setup logic ---------------------------------------------
class TracingSettings(BaseSettings):
    enabled: bool = True
    zipkin_endpoint: AnyHttpUrl = "http://jaeger:9411"

    class Config(CommonConfig):
        env_prefix = "TRACING_"


# Module's business logic ---------------------------------------------
