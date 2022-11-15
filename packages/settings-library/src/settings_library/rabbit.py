from functools import cached_property

from pydantic.networks import AnyUrl
from pydantic.types import SecretStr
from typing_extensions import TypedDict

from .base import BaseCustomSettings
from .basic_types import PortInt


class Channels(TypedDict):
    log: str
    progress: str
    instrumentation: str
    events: str


class RabbitDsn(AnyUrl):
    allowed_schemes = {"amqp"}


class RabbitSettings(BaseCustomSettings):
    # host
    RABBIT_HOST: str = "rabbit"
    RABBIT_PORT: PortInt = 5672

    # auth
    RABBIT_USER: str = "simcore"
    RABBIT_PASSWORD: SecretStr = SecretStr("simcore")

    @cached_property
    def dsn(self) -> str:
        return RabbitDsn.build(
            scheme="amqp",
            user=self.RABBIT_USER,
            password=self.RABBIT_PASSWORD.get_secret_value(),
            host=self.RABBIT_HOST,
            port=f"{self.RABBIT_PORT}",
        )
