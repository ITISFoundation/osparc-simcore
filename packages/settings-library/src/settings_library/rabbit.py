from functools import cached_property

from pydantic.networks import AnyUrl
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class RabbitDsn(AnyUrl):
    allowed_schemes = {"amqp", "amqps"}


class RabbitSettings(BaseCustomSettings):
    # host
    RABBIT_HOST: str
    RABBIT_PORT: PortInt = 5672
    RABBIT_SECURE: bool

    # auth
    RABBIT_USER: str
    RABBIT_PASSWORD: SecretStr

    @cached_property
    def dsn(self) -> str:
        rabbit_dsn: str = str(
            RabbitDsn.build(
                scheme="amqps" if self.RABBIT_SECURE else "amqp",
                username=self.RABBIT_USER,
                password=self.RABBIT_PASSWORD.get_secret_value(),
                host=self.RABBIT_HOST,
                port=self.RABBIT_PORT,
            )
        )
        return rabbit_dsn
