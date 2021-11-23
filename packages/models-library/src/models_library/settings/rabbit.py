import warnings
from typing_extensions import TypedDict

from pydantic import BaseSettings, Extra
from pydantic.networks import AnyUrl
from pydantic.types import PositiveInt, SecretStr


class Channels(TypedDict):
    log: str
    progress: str
    instrumentation: str
    events: str


warnings.warn(
    "models_library.settings will be mostly replaced by settings_library in future versions. "
    "SEE https://github.com/ITISFoundation/osparc-simcore/pull/2395 for details",
    DeprecationWarning,
)


class RabbitDsn(AnyUrl):
    allowed_schemes = {"amqp"}


class RabbitConfig(BaseSettings):
    # host
    host: str = "rabbit"
    port: PositiveInt = 5672

    # auth
    user: str = "simcore"
    password: SecretStr = SecretStr("simcore")

    # channels
    channels: Channels = {
        "log": "simcore.services.log",
        "progress": "simcore.services.progress",
        "instrumentation": "simcore.services.instrumentation",
        "events": "simcore.services.events",
    }

    @property
    def dsn(self) -> str:
        return RabbitDsn.build(
            scheme="amqp",
            user=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=f"{self.port}",
        )

    class Config:
        env_prefix = "RABBIT_"
        extra = Extra.forbid
