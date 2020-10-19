""" Basic configuration file for rabbitMQ

"""

from typing import Dict, Union

from pydantic import BaseSettings
from pydantic.types import SecretStr


class RabbitConfig(BaseSettings):
    name: str = "tasks"
    enabled: bool = True
    user: str = "simcore"
    password: str = "simcore"
    host: str = "rabbit"
    port: int = 5672
    channels: Dict[str, Union[str, Dict]] = {
        "log": "comp.backend.channels.log",
        "instrumentation": "comp.backend.channels.instrumentation",
        "celery": {"result_backend": "rpc://", "publication_timeout": 60},
    }

    class Config:
        env_prefix = "RABBIT_"

    @property
    def broker_url(self):
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}"

    @property
    def backend(self):
        return self.channels["celery"]["result_backend"]

    @property
    def publication_timeout(self):
        return self.channels["celery"]["publication_timeout"]


# TODO: create a CELERY config as well
