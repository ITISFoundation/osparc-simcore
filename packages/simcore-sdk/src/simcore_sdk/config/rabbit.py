""" Basic configuration file for rabbitMQ

"""

from typing import Dict, Union

import trafaret as T
from pydantic import BaseSettings

# TODO: adapt all data below!
CONFIG_SCHEMA = T.Dict(
    {
        T.Key("name", default="tasks", optional=True): T.String(),
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key("host", default="rabbit", optional=True): T.String(),
        T.Key("port", default=5672, optional=True): T.Int(),
        "user": T.String(),
        "password": T.String(),
        "channels": T.Dict(
            {
                "progress": T.String(),
                "log": T.String(),
                T.Key(
                    "celery", default=dict(result_backend="rpc://"), optional=True
                ): T.Dict(
                    {
                        T.Key(
                            "result_backend",
                            default="${CELERY_RESULT_BACKEND}",
                            optional=True,
                        ): T.String()
                    }
                ),
            }
        ),
    }
)
# TODO: use BaseSettings instead of BaseModel and remove trafaret ! -----------------------------------------------------------------------------
class Config(BaseSettings):
    name: str = "tasks"
    enabled: bool = True
    user: str = "simcore"
    password: str = "simcore"
    host: str = "rabbit"
    port: int = 5672
    channels: Dict[str, Union[str, Dict]] = {
        "progress": "comp.backend.channels.progress",
        "log": "comp.backend.channels.log",
        "celery": {"result_backend": "rpc://"},
    }

    class Config:
        env_prefix = "RABBIT_"

    @property
    def broker_url(self):
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}"

