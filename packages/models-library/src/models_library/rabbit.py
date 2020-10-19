from typing import Dict, Optional

from pydantic import BaseSettings, Extra
from pydantic.networks import AnyUrl
from pydantic.types import PositiveInt, SecretStr


class RabbitDsn(AnyUrl):
    allowed_schemes = {"amqp"}


class RabbitConfig(BaseSettings):
    dsn: Optional[RabbitDsn] = None

    # host
    host: str = "rabbit"
    port: PositiveInt = 5672

    # auth
    user: str = "simcore"
    password: SecretStr = SecretStr("simcore")

    # channels
    channels: Dict[str, str] = {
        "log": "comp.backend.channels.log",
        "instrumentation": "comp.backend.channels.instrumentation",
    }

    @property
    def rabbit_dsn(self):
        if self.dsn:
            return str(self.dsn)

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
