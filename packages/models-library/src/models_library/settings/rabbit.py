import warnings
from typing import Dict

from pydantic import BaseSettings, Extra
from pydantic.networks import AnyUrl
from pydantic.types import PositiveInt, SecretStr

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
    channels: Dict[str, str] = {
        "log": "comp.backend.channels.log",
        "progress": "comp.backend.channels.progress",
        "instrumentation": "comp.backend.channels.instrumentation",
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
