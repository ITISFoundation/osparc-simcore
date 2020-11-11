from typing import Dict, Optional

from pydantic import BaseSettings, Extra, validator
from pydantic.networks import AnyUrl
from pydantic.types import PositiveInt, SecretStr


class RabbitDsn(AnyUrl):
    allowed_schemes = {"amqp"}


class RabbitConfig(BaseSettings):
    # host
    host: str = "rabbit"
    port: PositiveInt = 5672

    # auth
    user: str = "simcore"
    password: SecretStr = SecretStr("simcore")

    dsn: Optional[RabbitDsn] = None

    # channels
    channels: Dict[str, str] = {
        "log": "comp.backend.channels.log",
        "instrumentation": "comp.backend.channels.instrumentation",
    }

    @validator("dsn", pre=True)
    @classmethod
    def autofill_dsn(cls, v, values):
        if not v and all(key in values for key in cls.__fields__ if key != "dsn"):
            return RabbitDsn.build(
                scheme="amqp",
                user=values["user"],
                password=values["password"].get_secret_value(),
                host=values["host"],
                port=f"{values['port']}",
            )
        return v

    class Config:
        env_prefix = "RABBIT_"
        extra = Extra.forbid
