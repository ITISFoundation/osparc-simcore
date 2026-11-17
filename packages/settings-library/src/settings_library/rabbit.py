from functools import cached_property
from typing import ClassVar

from pydantic.config import JsonDict
from pydantic.networks import AnyUrl
from pydantic.types import SecretStr
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings
from .basic_types import PortInt


class RabbitDsn(AnyUrl):
    allowed_schemes: ClassVar[set[str]] = {"amqp", "amqps"}


class RabbitSettings(BaseCustomSettings):
    # host
    RABBIT_HOST: str
    RABBIT_PORT: PortInt = 5672
    RABBIT_SECURE: bool
    # NOTE: "/" is RabbitMQ's default vhost; kept as default so existing deployments
    # (which never set this) produce the exact same DSN as before this field existed
    RABBIT_VHOST: str = "/"

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
                # omitted for the default vhost to keep the DSN unchanged for existing callers
                path=self.RABBIT_VHOST if self.RABBIT_VHOST != "/" else None,
            )
        )
        return rabbit_dsn

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "RABBIT_HOST": "rabbitmq.example.com",
                        "RABBIT_USER": "guest",
                        "RABBIT_PASSWORD": "guest-password",
                        "RABBIT_SECURE": False,
                        "RABBIT_PORT": 5672,
                    },
                    {
                        "RABBIT_HOST": "secure.rabbitmq.example.com",
                        "RABBIT_USER": "guest",
                        "RABBIT_PASSWORD": "guest-password",
                        "RABBIT_SECURE": True,
                        "RABBIT_PORT": 15672,
                    },
                ]
            }
        )

    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
        json_schema_extra=_update_json_schema_extra,
    )
